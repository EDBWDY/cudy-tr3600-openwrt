#!/usr/bin/env python3
"""Fail the build if the deliverables do not contain the requested features."""
import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from feature_requirements import requested_packages, verify_dnsmasq_nftset
from privacy_audit import audit_source, audit_image
from image_extraction import extract_for_audit

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'openwrt'
OUT = ROOT / 'artifacts'
OUT.mkdir(exist_ok=True)
source_privacy = audit_source(ROOT)
target = SRC / 'bin/targets/mediatek/filogic'
images = list(target.glob('*cudy_tr3600-v1*sysupgrade.bin'))
if len(images) != 1:
    raise RuntimeError(f'Expected exactly one TR3600 sysupgrade image: {images}')
image = images[0]
with tarfile.open(image) as archive:
    names = archive.getnames()
    prefix = 'sysupgrade-cudy_tr3600-v1/'
    if not all(prefix + entry in names for entry in ['CONTROL', 'kernel', 'root']):
        raise RuntimeError('Incorrect sysupgrade board archive layout')
manifest = image.with_name(image.name.replace('-squashfs-sysupgrade.bin', '.manifest'))
if not manifest.exists():
    matches = list(target.glob('*cudy_tr3600-v1*.manifest'))
    if len(matches) != 1:
        raise RuntimeError(f'Missing unique device manifest: {matches}')
    manifest = matches[0]
packages = {}
for line in manifest.read_text().splitlines():
    if line.strip():
        parts = line.split()
        version = parts[2:] if len(parts) > 1 and parts[1] == '-' else parts[1:]
        packages[parts[0]] = ' '.join(version)
required, build_options = requested_packages(
    (ROOT / 'config.seed').read_text(), (SRC / '.config').read_text())
missing = [name for name in required if name not in packages]
if missing:
    raise RuntimeError(f'Requested packages missing from firmware manifest: {missing}')
kernel = packages.get('kernel', '')
if not kernel.startswith('6.12.94'):
    raise RuntimeError(f'Unexpected kernel version: {kernel}')
metadata_path = OUT / 'sysupgrade-metadata.json'
subprocess.run([str(SRC / 'staging_dir/host/bin/fwtool'), '-i', str(metadata_path), str(image)], check=True)
metadata = json.loads(metadata_path.read_text())
if 'cudy,tr3600-v1' not in metadata.get('supported_devices', []):
    raise RuntimeError(f'Incorrect device metadata: {metadata}')
if image.stat().st_size > 237824 * 1024:
    raise RuntimeError('Firmware exceeds the TR3600 device image size limit')
audit = ROOT / 'image-audit'
audit.mkdir()
with tarfile.open(image) as archive:
    with archive.extractfile(prefix + 'root') as source, (audit / 'root.squashfs').open('wb') as output:
        shutil.copyfileobj(source, output)
# The audit reads ordinary files; recreating /dev/console requires root and is
# unnecessary. Exclude that exact device node, keeping every other error fatal.
extract_for_audit(SRC / 'staging_dir/host/bin/unsquashfs4', audit / 'root.squashfs', audit / 'root')
rootfs = audit / 'root'
dnsmasq_features = verify_dnsmasq_nftset((rootfs / 'usr/sbin/dnsmasq').read_bytes())
if 'nftables-json' not in packages:
    raise RuntimeError('dnsmasq nftset dependency nftables-json is missing')
required_files = [
    'usr/libexec/interface-identity', 'usr/libexec/wan-identity',
    'usr/libexec/rpcd/interface.identity', 'www/cgi-bin/wan-identity-client',
    'www/luci-static/resources/view/network/interface_identity_v5.js',
    'usr/libexec/tr3600-clients', 'usr/libexec/rpcd/tr3600.clients',
    'usr/share/tr3600-clients/engine.uc', 'etc/init.d/tr3600-clients',
    'usr/share/luci/menu.d/luci-app-tr3600-clients.json',
    'usr/share/rpcd/acl.d/luci-app-tr3600-clients.json',
    'www/luci-static/resources/view/status/tr3600-clients.js',
    'www/luci-static/resources/view/status/tr3600-clients-v1_0_16.js',
    'usr/libexec/turboacc-control', 'usr/libexec/turboacc-wed',
    'usr/libexec/rpcd/luci.turboacc', 'etc/init.d/turboacc', 'etc/config/turboacc',
    'usr/share/luci/menu.d/luci-app-turboacc.json',
    'usr/share/rpcd/acl.d/luci-app-turboacc.json',
    'usr/share/turboacc/port-manifest.json',
    'www/luci-static/resources/view/turboacc.js',
    'www/luci-static/resources/turboacc_safety.js',
    'www/luci-static/resources/turboacc_wed.js',
    'www/luci-static/resources/view/services/adguardhome.js',
    'www/luci-static/resources/tr3600-clients.css',
    'usr/libexec/tr3600-fan', 'usr/libexec/rpcd/tr3600.usb',
    'etc/init.d/tr3600-fan', 'etc/config/tr3600_fan',
    'usr/share/luci/menu.d/luci-app-tr3600-fan.json',
    'usr/share/luci/menu.d/luci-app-tr3600-usb.json',
    'usr/share/rpcd/acl.d/luci-app-tr3600-fan.json',
    'usr/share/rpcd/acl.d/luci-app-tr3600-usb.json',
    'www/luci-static/resources/view/system/tr3600-fan.js',
    'www/luci-static/resources/view/system/tr3600-usb.js',
    'www/luci-static/resources/view/system/tr3600-usb-v1_1_1.js',
    'www/luci-static/resources/tr3600_usb_status.js',
    'www/luci-static/resources/view/status/tr3600_usb.js',
    'www/luci-static/resources/view/status/include/35_tr3600_usb.js',
    'www/luci-static/resources/view/samba4-tr3600-v2.js',
    'www/luci-static/resources/view/system/mounts-tr3600-v1.js',
    'usr/share/luci/menu.d/luci-app-https-dns-proxy.json',
    'www/luci-static/resources/view/https-dns-proxy/overview.js',
    'usr/libexec/rpcd/luci.https-dns-proxy',
    'etc/init.d/https-dns-proxy', 'usr/sbin/https-dns-proxy',
    'etc/openclash/core/clash_meta', 'etc/uci-defaults/99-tr3600-custom'
]
for name in required_files:
    if not (rootfs / name).is_file():
        raise RuntimeError(f'Required installed file is missing: {name}')
for name in ['https-dns-proxy', 'libcares', 'libev']:
    if name not in packages:
        raise RuntimeError('DoH backend dependency missing: ' + name)
for package in ['luci-app-tr3600-usb', 'luci-app-tr3600-fan', 'luci-app-tr3600-clients', 'luci-app-network-identity', 'luci-app-router-adguardhome']:
    source_files = ROOT / 'package' / package / 'files'
    for file in source_files.rglob('*'):
        if file.is_file() and (rootfs / file.relative_to(source_files)).read_bytes() != file.read_bytes():
            raise RuntimeError('Installed custom plugin differs from current source: ' + str(file))
# Verify the new controller, guarded NAT choices and matched port provenance.
def installed_luci_javascript(source):
    data = source.read_bytes()
    if 'CONFIG_LUCI_JSMIN=y' in (SRC / '.config').read_text().splitlines():
        # Match the pinned luci.mk JsMin transformation, using the exact host
        # tool preserved in this compiler checkpoint. Never weaken this to a
        # substring/whitespace comparison, which could hide modified code.
        # LuCI's host package installs this in hostpkg; tools built by OpenWrt's
        # tools stage use host. Resolve only within the authenticated checkpoint.
        candidates = [SRC / 'staging_dir' / directory / 'bin/jsmin'
                      for directory in ('hostpkg', 'host')]
        tool = next((path for path in candidates if path.is_file()), None)
        if tool is None:
            raise RuntimeError('Preserved LuCI jsmin host tool missing: ' + str(candidates))
        data = subprocess.run([str(tool)], input=data, capture_output=True, check=True).stdout
    return data


for name, relative in {
    'turboacc-control':'usr/libexec/turboacc-control',
    'turboacc-ui':'usr/libexec/turboacc-ui',
    'turboacc_cards.js':'www/luci-static/resources/view/turboacc_cards_v3.js',
    'turboacc_cards.css':'www/luci-static/resources/turboacc_cards_v3.css',
    'turboacc-wed':'usr/libexec/turboacc-wed',
    'turboacc.rpc':'usr/libexec/rpcd/luci.turboacc',
    'turboacc_safety.js':'www/luci-static/resources/turboacc_safety.js',
    'turboacc_wed.js':'www/luci-static/resources/turboacc_wed.js',
}.items():
    original = ROOT / 'experiments/turboacc' / name
    expected = installed_luci_javascript(original) if original.suffix == '.js' else original.read_bytes()
    if (rootfs / relative).read_bytes() != expected:
        raise RuntimeError('TurboACC installed source differs: ' + name)
frontend = SRC / 'package/custom/luci-app-turboacc-mtk/htdocs/luci-static/resources/view/turboacc.js'
if (rootfs / 'www/luci-static/resources/view/turboacc.js').read_bytes() != installed_luci_javascript(frontend):
    raise RuntimeError('TurboACC installed frontend differs from its pinned build input')
if (rootfs / 'usr/share/luci/menu.d/luci-app-tr3600-acceleration.json').exists():
    raise RuntimeError('Obsolete acceleration controller must not coexist with TurboACC')
cone = (rootfs / 'etc/config/turboacc').read_text()
for expected in ["option fullcone '0'", "option fullcone_protocol 'udp'", "option wed_enable '0'"]:
    if expected not in cone:
        raise RuntimeError('Unsafe acceleration first-boot default: ' + expected)
installed_port=json.loads((rootfs/'usr/share/turboacc/port-manifest.json').read_text())
compiled_port=json.loads((SRC/'acceleration-port-manifest.json').read_text())
if installed_port != compiled_port or installed_port['hardware_runtime_verified']:
    raise RuntimeError('Acceleration port provenance or physical verification claim differs')
samba = json.loads((rootfs / 'usr/share/luci/menu.d/luci-app-samba4.json').read_text())['admin/services/samba4']
if samba['title'] != 'Samba' or samba['action']['path'] != 'samba4-tr3600-v2':
    raise RuntimeError('Samba menu presentation update is missing')
mount_menu = json.loads((rootfs / 'usr/share/luci/menu.d/luci-mod-system.json').read_text())
if mount_menu['admin/system/mounts']['action']['path'] != 'system/mounts-tr3600-v1':
    raise RuntimeError('Mount page presentation update is missing')
from mount_labels import BUTTON_LABEL, DESCRIPTION
mount_script = (rootfs / 'www/luci-static/resources/view/system/mounts-tr3600-v1.js').read_text()
if BUTTON_LABEL not in mount_script or DESCRIPTION not in mount_script:
    raise RuntimeError('Clarified mount action label is missing')
defaults = (rootfs / 'etc/uci-defaults/99-tr3600-custom').read_text()
if '/etc/init.d/https-dns-proxy disable' not in defaults:
    raise RuntimeError('DoH must remain disabled at first boot')
image_privacy = audit_image(rootfs)
(OUT / 'privacy-verification.json').write_text(json.dumps({
    'source': source_privacy, 'image': image_privacy,
    'doh_first_boot': 'disabled',
}, indent=2) + '\n')
core_header = (rootfs / 'etc/openclash/core/clash_meta').read_bytes()[:20]
if core_header[:4] != b'\x7fELF' or int.from_bytes(core_header[18:20], 'little') != 183:
    raise RuntimeError('Installed mihomo is not an AArch64 ELF binary')
for binary in ['tailscale', 'tailscaled', 'zerotier-one', 'usbmuxd', 'idevicepair', 'smbd', 'AdGuardHome']:
    if not any((rootfs / directory / binary).exists() for directory in ['usr/bin', 'usr/sbin', 'bin', 'sbin']):
        raise RuntimeError(f'Required VPN/storage/pairing executable missing: {binary}')
module_names = {path.name for path in (rootfs / 'lib/modules').rglob('*.ko')}
required_modules = ['usb-storage.ko', 'uas.ko', 'rndis_host.ko', 'cdc_ether.ko', 'cdc_ncm.ko', 'ipheth.ko', 'ntfs3.ko', 'exfat.ko', 'vfat.ko']
if any(name not in module_names for name in required_modules):
    raise RuntimeError(f'USB/filesystem modules missing: {set(required_modules) - module_names}')
# Compilation already preserved images, matching packages and their hashes via
# collect-unverified.py. Independent verification produces reports only; never
# repack or replace those deliverables when repairing or rerunning a verifier.
verification = {
    'board': 'cudy,tr3600-v1', 'kernel': kernel,
    'required_packages': required, 'required_build_options': build_options,
    'dnsmasq_compile_options': dnsmasq_features, 'verified_package_count': len(packages),
    'image_bytes': image.stat().st_size,
    'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
    'installed_files_checked': required_files, 'required_modules_checked': required_modules,
    'validation': 'Archive, metadata, device manifest, installed plugin/core files and USB modules checked; not yet flashed or runtime tested.'
}
(OUT / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
print(json.dumps(verification, indent=2))
