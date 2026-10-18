#!/usr/bin/env python3
"""Prepare a pinned OpenWrt build without importing any router credentials."""
import gzip
import hashlib
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'openwrt'
LOCK = json.loads((ROOT / 'sources.json').read_text())
from privacy_audit import audit_source
audit_source(ROOT)


def run(*args, cwd=ROOT):
    subprocess.run(args, cwd=cwd, check=True)


def checkout(spec, dest):
    if dest.exists():
        raise RuntimeError(f'Refusing to overwrite existing source tree: {dest}')
    dest.mkdir(parents=True)
    run('git', 'init', '-q', str(dest))
    run('git', '-C', str(dest), 'fetch', '--depth', '1', spec['url'], spec['commit'])
    run('git', '-C', str(dest), 'checkout', '--detach', 'FETCH_HEAD')


checkout(LOCK['openwrt'], SRC)
run('git', 'apply', '--check', str(ROOT / 'patches/cudy-tr3600-v1-fixes.patch'), cwd=SRC)
run('git', 'apply', str(ROOT / 'patches/cudy-tr3600-v1-fixes.patch'), cwd=SRC)
feeds = [f"src-git {name} {spec['url']}^{spec['commit']}" for name, spec in LOCK['feeds'].items()]
(SRC / 'feeds.conf').write_text('\n'.join(feeds) + '\n')
run('./scripts/feeds', 'update', '-a', cwd=SRC)
run('./scripts/feeds', 'install', '-a', cwd=SRC)
# This pinned LuCI app selects weechat-minimal while depending on weechat-full,
# which creates a Kconfig cycle with the pinned packages feed. It is not part of
# this firmware. Exclude its feed link, without changing either pinned source.
weechat = SRC / 'package/feeds/luci/luci-app-weechat'
if weechat.is_symlink():
    weechat.unlink()

from samba_labels import customize_package
customize_package(SRC / 'feeds/luci/applications/luci-app-samba4')

from mount_labels import customize_package as customize_mounts
customize_mounts(SRC / 'feeds/luci/modules/luci-mod-system')

from channel_graph import customize_package as customize_channel_graph
customize_channel_graph(SRC / 'feeds/luci/modules/luci-mod-status')
from service_controls import customize_package as customize_service_controls
customize_service_controls(SRC / 'feeds/luci/applications/luci-app-https-dns-proxy')

# Build the same pinned Rust release for this x86_64 host and AArch64 router.
# Avoid compiling unused LLVM backends and duplicating static LLVM in each tool.
rust_makefile = SRC / 'feeds/packages/lang/rust/Makefile'
rust_data = rust_makefile.read_text()
rust_marker = '\t--set=llvm.download-ci-llvm=false \\\n'
if rust_data.count(rust_marker) != 1:
    raise RuntimeError('Pinned Rust configure layout changed')
rust_data = rust_data.replace(rust_marker, rust_marker +
    '\t--set=llvm.targets="AArch64;X86" \\\n'
    '\t--set=llvm.experimental-targets= \\\n'
    '\t--set=llvm.link-shared=true \\\n'
    '\t--set=llvm.link-jobs=1 \\\n')
rust_makefile.write_text(rust_data)

vendor = ROOT / 'vendor'
for name, spec in LOCK['plugins'].items():
    checkout(spec, vendor / name)

dest = SRC / 'package/custom'
dest.mkdir()
for package in (ROOT / 'package').iterdir():
    shutil.copytree(package, dest / package.name)
for name, origin in {
    'luci-app-openclash': vendor / 'openclash/luci-app-openclash',
    'luci-theme-argon': vendor / 'argon',
    'luci-app-argon-config': vendor / 'argon_config',
    'luci-app-zerotier': vendor / 'immortal_luci/applications/luci-app-zerotier',
}.items():
    shutil.copytree(origin, dest / name, ignore=shutil.ignore_patterns('.git', '.github'))
    makefile = dest / name / 'Makefile'
    data = makefile.read_text().replace('include ../../luci.mk', 'include $(TOPDIR)/feeds/luci/luci.mk')
    if name == 'luci-app-openclash':
        data = data.replace('PKG_VERSION:=', 'PKG_BUILD_DEPENDS:=luci-base/host\nPKG_VERSION:=', 1)
    makefile.write_text(data)

# Use the previously verified GUI adaptation for the official ZeroTier daemon.
from theme_customizations import customize_theme
customize_theme(dest / 'luci-theme-argon')
from tailscale_tables import customize_sources as customize_tailscale_tables
customize_tailscale_tables(SRC)

zt_configs = list((dest / 'luci-app-zerotier/htdocs').rglob('config.js'))
if len(zt_configs) != 1:
    raise RuntimeError(f'Unexpected ZeroTier GUI layout: {zt_configs}')
shutil.copyfile(ROOT / 'zerotier-config.openwrt.js', zt_configs[0])

core = LOCK['mihomo']
request = urllib.request.Request(core['url'], headers={'User-Agent': 'TR3600-custom-build'})
with urllib.request.urlopen(request, timeout=120) as response:
    archive = response.read()
if hashlib.sha256(archive).hexdigest() != core['sha256']:
    raise RuntimeError('mihomo checksum mismatch')
core_dir = dest / 'tr3600-mihomo/files'
core_dir.mkdir()
core_binary = core_dir / 'clash_meta'
core_binary.write_bytes(gzip.decompress(archive))
core_binary.chmod(0o755)

shutil.copytree(ROOT / 'files', SRC / 'files')
for package in ['luci-app-tr3600-fan', 'luci-app-tr3600-usb', 'luci-app-tr3600-clients', 'luci-app-tr3600-acceleration', 'luci-app-network-identity']:
    for path in (dest / package / 'files').rglob('*'):
        if path.is_file() and ('init.d' in path.parts or 'libexec' in path.parts or 'cgi-bin' in path.parts):
            path.chmod(0o755)
for path in (SRC / 'files/etc/uci-defaults').iterdir():
    path.chmod(0o755)
shutil.copyfile(ROOT / 'config.seed', SRC / '.config')
# Apply the paired, compile- and packet-tested backend before defconfig.
# This changes compiler inputs only; it never contacts a running router.
import sys
sys.path.insert(0, str(ROOT / 'experiments/turboacc'))
from integrate_openwrt import integrate
integrate(SRC)
run('make', 'defconfig', cwd=SRC)
config = set((SRC / '.config').read_text().splitlines())
requested = [line for line in (ROOT / 'config.seed').read_text().splitlines() if line.startswith('CONFIG_') and line.endswith('=y')]
missing = [line for line in requested if line not in config]
if missing:
    raise RuntimeError(f'Requested features were dropped by defconfig: {missing}')
print('All explicitly requested packages and target options survived defconfig.')
