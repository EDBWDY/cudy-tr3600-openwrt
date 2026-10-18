#!/usr/bin/env python3
"""Verify already uploaded firmware and exact package payloads without building."""
import argparse
import ast
import hashlib
import json
import posixpath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path
from feature_requirements import requested_packages, verify_dnsmasq_nftset
from privacy_audit import audit_source, audit_image
from mount_labels import BUTTON_LABEL, DESCRIPTION
from image_extraction import extract_for_audit
from kernel_audit import verify_fit_kernel

RECIPE = Path(__file__).resolve().parents[1]


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('--audit', type=Path, default=Path('downloaded-image-audit'))
    parser.add_argument('--output', type=Path, default=Path('verified-artifacts'))
    parser.add_argument('--rootfs', type=Path, help='Existing independent extraction for local diagnostics')
    parser.add_argument('--inventory', type=Path, help='Independent SquashFS inventory with original modes/symlinks')
    args = parser.parse_args()
    art, audit, out = args.artifacts.resolve(), args.audit.resolve(), args.output.resolve()
    source_privacy = audit_source(RECIPE)
    for line in (art / 'artifact-sha256sums').read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        if Path(name).name != name or sha256(art / name) != digest:
            raise RuntimeError('Artifact SHA256 mismatch or unsafe filename: ' + name)
    for name in ['config.seed', 'sources.json']:
        if (art / name).read_bytes() != (RECIPE / name).read_bytes():
            raise RuntimeError('Downloaded build inputs differ: ' + name)
    if (art / 'hardware-fixes.patch').read_bytes() != (RECIPE / 'patches/cudy-tr3600-v1-fixes.patch').read_bytes():
        raise RuntimeError('Downloaded hardware fixes differ')
    images = list(art.glob('*cudy_tr3600-v1*sysupgrade.bin'))
    if len(images) != 1:
        raise RuntimeError('Expected unique TR3600 v1 sysupgrade image')
    image = images[0]
    if image.stat().st_size > 237824 * 1024:
        raise RuntimeError('Image exceeds device limit')
    audit.mkdir(parents=True, exist_ok=False)
    with tarfile.open(image) as t:
        prefix = 'sysupgrade-cudy_tr3600-v1/'
        for entry in ['CONTROL', 'kernel', 'root']:
            data = t.extractfile(prefix + entry).read()
            (audit / ('image-' + entry)).write_bytes(data)
    kernel_audit = verify_fit_kernel((audit / 'image-kernel').read_bytes())
    tail = image.read_bytes()[-8192:].decode('utf-8', 'replace')
    metadata = []
    for match in re.finditer(r'\{\s*"metadata_version"', tail):
        try:
            metadata.append(json.JSONDecoder().raw_decode(tail[match.start():])[0])
        except ValueError:
            pass
    if len(metadata) != 1 or 'cudy,tr3600-v1' not in metadata[0].get('supported_devices', []):
        raise RuntimeError('Invalid device metadata')
    root = args.rootfs.resolve() if args.rootfs else audit / 'rootfs'
    if not args.rootfs:
        extract_for_audit('unsquashfs', audit / 'image-root', root)
    packages = {}
    for block in (root / 'lib/apk/db/installed').read_text(encoding='utf-8').split('\n\n'):
        fields = dict(line.split(':', 1) for line in block.splitlines() if ':' in line and len(line.split(':', 1)[0]) == 1)
        if 'P' in fields:
            packages[fields['P']] = fields['V']
    required, options = requested_packages((art / 'config.seed').read_text(encoding='utf-8'), (art / 'config.full').read_text(encoding='utf-8'))
    if set(required) - packages.keys() or not packages['kernel'].startswith('6.12.94~'):
        raise RuntimeError('Actual rootfs lacks requested packages or correct kernel')
    dnsmasq = verify_dnsmasq_nftset((root / 'usr/sbin/dnsmasq').read_bytes())
    tree = ast.parse((RECIPE / 'scripts/verify.py').read_text(encoding='utf-8'))
    required_files = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(v, ast.Name) and v.id == 'required_files' for v in n.targets))
    external_inventory = {i['path']: i for i in json.loads(args.inventory.read_text(encoding='utf-8'))} if args.inventory else {}
    def image_path(name):
        # Windows independent extraction retains symlinks as inventory entries.
        visited = set()
        while not (root / name).is_file() and name in external_inventory and name not in visited:
            visited.add(name)
            item = external_inventory[name]
            if item['type'] != 'symlink':
                break
            target = item['target']
            name = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(name), target))
            if name == '..' or name.startswith('../'):
                raise RuntimeError('Image symlink escapes its root')
        return root / name
    for name in required_files:
        if not image_path(name).is_file():
            raise RuntimeError('Actual installed file missing: ' + name)
    for package in ['luci-app-tr3600-usb', 'luci-app-tr3600-fan', 'luci-app-tr3600-clients', 'luci-app-tr3600-acceleration', 'luci-app-network-identity']:
        source = RECIPE / 'package' / package / 'files'
        for f in source.rglob('*'):
            if f.is_file() and (root / f.relative_to(source)).read_bytes() != f.read_bytes():
                raise RuntimeError('Custom plugin differs from current source: ' + str(f.relative_to(source)))
    samba = json.loads((root / 'usr/share/luci/menu.d/luci-app-samba4.json').read_text(encoding='utf-8'))['admin/services/samba4']
    if samba['title'] != 'Samba' or samba['action']['path'] != 'samba4-tr3600-v2':
        raise RuntimeError('Samba menu update missing')
    if 'Samba' not in (root / 'www/luci-static/resources/view/samba4-tr3600-v2.js').read_text(encoding='utf-8'):
        raise RuntimeError('Samba page title missing')
    menu = json.loads((root / 'usr/share/luci/menu.d/luci-mod-system.json').read_text(encoding='utf-8'))
    mount = (root / 'www/luci-static/resources/view/system/mounts-tr3600-v1.js').read_text(encoding='utf-8')
    if menu['admin/system/mounts']['action']['path'] != 'system/mounts-tr3600-v1' or BUTTON_LABEL not in mount or DESCRIPTION not in mount:
        raise RuntimeError('Clarified configured-partition mount action missing')
    defaults = (root / 'etc/uci-defaults/99-tr3600-custom').read_text(encoding='utf-8')
    if '/etc/init.d/https-dns-proxy disable' not in defaults:
        raise RuntimeError('DoH first-boot disable missing')
    image_privacy = audit_image(root)
    for name in ['usb-storage', 'uas', 'rndis_host', 'cdc_ether', 'cdc_ncm',
                 'cdc_mbim', 'qmi_wwan', 'ipheth', 'r8152', 'ntfs3', 'exfat', 'vfat']:
        if not list((root / 'lib/modules').rglob(name + '.ko')):
            raise RuntimeError('Required driver missing: ' + name)
    core = (root / 'etc/openclash/core/clash_meta').read_bytes()
    if core[:6] != b'\x7fELF\x02\x01' or int.from_bytes(core[18:20], 'little') != 183:
        raise RuntimeError('Mihomo must be an AArch64 ELF')
    inventory = []
    for p in root.rglob('*'):
        mode = p.lstat().st_mode
        item = {'path': p.relative_to(root).as_posix(), 'mode': oct(mode),
                'type': 'symlink' if stat.S_ISLNK(mode) else 'file' if stat.S_ISREG(mode) else 'dir' if stat.S_ISDIR(mode) else 'other'}
        if p.is_symlink():
            item['target'] = str(p.readlink())
        inventory.append(item)
    inventory_path = args.inventory.resolve() if args.inventory else audit / 'rootfs-files.json'
    if not args.inventory:
        inventory_path.write_text(json.dumps(inventory), encoding='utf-8')
    subprocess.run([sys.executable, str(RECIPE / 'scripts/audit_package_payloads.py'), str(audit),
                    '--rootfs', str(root), '--artifacts', str(art), '--inventory', str(inventory_path)], check=True)
    matching = json.loads((audit / 'matching-packages-verification.json').read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=False)
    for p in art.iterdir():
        if p.is_file():
            shutil.copyfile(p, out / p.name)
    report = {'board': 'cudy,tr3600-v1', 'firmware_sha256': sha256(image),
              'kernel_abi': packages['kernel'], 'kernel_audit': kernel_audit,
              'required_packages': len(required), 'actual_packages': len(packages),
              'kernel_packages_verified': matching['kernel_packages_verified'],
              'module_payloads_identical': matching['module_payloads_identical'],
              'dnsmasq_compile_options': dnsmasq, 'build_options': options,
              'source_privacy': source_privacy, 'image_privacy': image_privacy,
              'mount_button': BUTTON_LABEL, 'mount_description': DESCRIPTION,
              'doh_first_boot': 'disabled', 'runtime_tested': False,
              'scope': 'Previously uploaded firmware independently audited; no compiler or firmware program executed'}
    (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    shutil.copyfile(audit / 'matching-packages-verification.json', out / 'matching-packages-verification.json')
    (out / 'artifact-sha256sums').write_text('\n'.join(f'{sha256(p)}  {p.name}' for p in sorted(out.iterdir())
                                                   if p.is_file() and p.name != 'artifact-sha256sums') + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
