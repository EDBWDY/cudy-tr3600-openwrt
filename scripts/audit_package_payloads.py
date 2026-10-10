"""Audit the actual same-build APK payloads against the extracted firmware."""
import hashlib
import json
import posixpath
import re
import struct
import tarfile
import zlib
from pathlib import Path
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('base', type=Path)
parser.add_argument('--rootfs', type=Path)
parser.add_argument('--artifacts', type=Path)
parser.add_argument('--inventory', type=Path)
args = parser.parse_args()
BASE = args.base.resolve()
ROOT = args.rootfs.resolve() if args.rootfs else BASE / 'rootfs'
ARTIFACTS = args.artifacts.resolve() if args.artifacts else BASE / 'artifacts'
INVENTORY = args.inventory.resolve() if args.inventory else BASE / 'rootfs-files.json'
installed = {}
kernel_dependencies = {}
for block in (ROOT / 'lib/apk/db/installed').read_text(encoding='utf-8').split('\n\n'):
    fields = dict(line.split(':', 1) for line in block.splitlines() if ':' in line and len(line.split(':', 1)[0]) == 1)
    if 'P' in fields:
        installed[fields['P']] = fields['V']
        kernel_dependencies[fields['P']] = [s for s in fields.get('D', '').split() if s.startswith('kernel=')]
abi = installed['kernel']
manifest = {}
for line in next(ARTIFACTS.glob('*cudy_tr3600-v1.manifest')).read_text().splitlines():
    name, version = line.split(' - ', 1)
    manifest[name] = version
assert manifest == installed, 'Manifest differs from actual rootfs APK database'
modules = {p.name: p.read_bytes() for p in (ROOT / 'lib/modules').rglob('*.ko')}
matched_modules = set()
checked = {}

def blocks(data):
    assert data.startswith(b'ADB.pckg'), 'Expected APK v3 package schema'
    offset = 8
    result = []
    while offset < len(data):
        word, = struct.unpack_from('<I', data, offset)
        size, kind = word & 0x3fffffff, word >> 30
        assert size >= 4 and offset + size <= len(data), 'Invalid APK block extent'
        result.append((kind, data[offset + 4:offset + size]))
        offset = (offset + size + 7) & ~7
    assert offset == len(data), 'Invalid APK block alignment'
    return result

with tarfile.open(ARTIFACTS / 'same-build-packages.tar.gz') as archive:
    for member in archive.getmembers():
        if not member.isfile() or not member.name.endswith('.apk'):
            continue
        candidates = [name for name, version in installed.items() if Path(member.name).name == f'{name}-{version}.apk']
        assert len(candidates) == 1, f'Unexpected package name/version: {member.name}'
        name = candidates[0]
        assert name not in checked, f'Duplicate archived package {name}'
        compressed = archive.extractfile(member).read()
        assert compressed.startswith(b'ADBd'), f'Unexpected APK compression {name}'
        decoder = zlib.decompressobj(-15)
        decoded = decoder.decompress(compressed[4:]) + decoder.flush()
        assert decoder.eof and not decoder.unused_data, f'Incomplete APK stream {name}'
        package_blocks = blocks(decoded)
        metadata_blocks = [data for kind, data in package_blocks if kind == 0]
        assert len(metadata_blocks) == 1
        metadata = metadata_blocks[0]
        # APK ADB short blobs encode length immediately before their bytes.
        for value in (name, installed[name]):
            encoded = value.encode()
            assert len(encoded) < 128 and bytes([len(encoded)]) + encoded in metadata, f'APK identity mismatch {name}'
        if name.startswith('kmod-'):
            assert kernel_dependencies[name] == ['kernel=' + abi], f'Rootfs kernel dependency mismatch {name}'
            assert b'\x06kernel' + bytes([len(abi)]) + abi.encode() in metadata, f'Archived kernel ABI mismatch {name}'
        payloads = [data[8:] for kind, data in package_blocks if kind == 2]
        if name.startswith('kmod-'):
            for module_name, content in modules.items():
                if content in payloads:
                    assert content[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', content, 18)[0] == 183
                    assert b'vermagic=6.12.94 SMP mod_unload aarch64\0' in content, module_name
                    matched_modules.add(module_name)
        checked[name] = {'version': installed[name], 'sha256': hashlib.sha256(compressed).hexdigest()}
assert set(checked) == set(installed), f'Installed packages absent from archive: {set(installed) - set(checked)}'
assert matched_modules == set(modules), f'Rootfs modules absent from package payloads: {set(modules) - matched_modules}'
files = {item['path']: item for item in json.loads(INVENTORY.read_text(encoding='utf-8'))}
def executable(path):
    visited = set()
    while path in files and path not in visited:
        visited.add(path)
        item = files[path]
        if item['type'] == 'file':
            return bool(int(item['mode'], 8) & 0o111)
        if item['type'] != 'symlink':
            return False
        target = item['target']
        path = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(path), target))
        assert path != '..' and not path.startswith('../'), 'Executable symlink escapes image root'
    return False
for path in ['etc/init.d/tr3600-fan', 'etc/config/tr3600_fan',
             'usr/share/luci/menu.d/luci-app-tr3600-fan.json', 'usr/share/luci/menu.d/luci-app-tr3600-usb.json',
             'usr/share/rpcd/acl.d/luci-app-tr3600-fan.json', 'usr/share/rpcd/acl.d/luci-app-tr3600-usb.json',
             'etc/uci-defaults/99-tr3600-custom']:
    assert path in files and files[path]['type'] == 'file', path
for binary in ['tailscale', 'tailscaled', 'zerotier-one', 'usbmuxd', 'idevicepair', 'smbd']:
    paths = [f'{directory}/{binary}' for directory in ['usr/bin', 'usr/sbin', 'bin', 'sbin']]
    assert any(executable(p) for p in paths), binary
images = list(ARTIFACTS.glob('*cudy_tr3600-v1*sysupgrade.bin'))
assert len(images) == 1 and images[0].stat().st_size <= 237824 * 1024
result = {'kernel_abi': abi, 'packages_verified': len(checked),
          'kernel_packages_verified': sum(name.startswith('kmod-') for name in checked),
          'module_payloads_identical': len(matched_modules),
          'result': 'Every installed package is archived; all kernel dependencies match; every installed module equals its archived payload',
          'packages': checked}
(BASE / 'matching-packages-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key != 'packages'}, indent=2))
