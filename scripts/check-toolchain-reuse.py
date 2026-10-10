#!/usr/bin/env python3
"""Fail early if restored GCC/Rust cannot be used without a toolchain rebuild."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'openwrt'


def one(pattern):
    paths = list(SRC.glob(pattern))
    if len(paths) != 1:
        raise RuntimeError(f'Expected one complete toolchain component: {pattern}: {paths}')
    return paths[0]


def main():
    one('staging_dir/toolchain-*/stamp/.gcc_final_installed')
    one('staging_dir/hostpkg/stamp/.rust_installed')
    one('build_dir/target-*/host/rustc-*/.built')
    gcc = one('staging_dir/toolchain-*/bin/aarch64-openwrt-linux-musl-gcc')
    rust = one('staging_dir/target-*/host/bin/rustc')
    target = subprocess.check_output([str(gcc), '-dumpmachine'], text=True).strip()
    version = subprocess.check_output([str(rust), '--version'], text=True).strip()
    if target != 'aarch64-openwrt-linux-musl' or not version.startswith('rustc 1.96.0 '):
        raise RuntimeError(f'Unexpected saved compiler: {target}; {version}')
    log = ROOT / 'toolchain-reuse.log'
    # Run actual dependency checks: make -n can falsely schedule work because
    # OpenWrt's dependency checks themselves are phony targets.
    with log.open('w', encoding='utf-8') as output:
        result = subprocess.run(['timeout', '--kill-after=15s', '120s', 'make', '-j2', 'V=s',
                                 'toolchain/install', 'package/feeds/packages/rust/host/compile'],
                                cwd=SRC, stdout=output, stderr=subprocess.STDOUT)
    data = log.read_text(encoding='utf-8', errors='replace')
    if result.returncode != 0:
        raise RuntimeError(f'Toolchain reuse check did not complete in two minutes: {result.returncode}; see {log}')
    if re.search(r'Building stage[12] compiler|Building C(?:XX)? object|(?:gcc|g\+\+|clang)(?:["\s]).*\s-c\s', data):
        raise RuntimeError('Reuse check attempted compiler rebuild; refusing full firmware compile')
    report = {'gcc_target': target, 'rust_version': version,
              'dependency_check_exit': result.returncode,
              'result': 'Existing toolchain usable; no compiler rebuild observed'}
    (ROOT / 'toolchain-reuse.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
