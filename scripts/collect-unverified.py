#!/usr/bin/env python3
"""Save produced images and matching packages BEFORE any feature verifier runs."""
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'openwrt'
TARGET = SRC / 'bin/targets/mediatek/filogic'
OUT = ROOT / 'unverified-artifacts'
images = list(TARGET.glob('*cudy_tr3600-v1*sysupgrade.bin'))
if not images:
    print('No TR3600 sysupgrade image produced yet; checkpoint is the recovery path')
else:
    OUT.mkdir(exist_ok=False)
    for path in TARGET.iterdir():
        if path.is_file():
            shutil.copyfile(path, OUT / path.name)
    for origin, name in ((SRC / '.config', 'config.full'), (ROOT / 'config.seed', 'config.seed'),
                         (ROOT / 'sources.json', 'sources.json'),
                         (SRC / 'feeds/packages/lang/rust/Makefile', 'rust-host.Makefile'),
                         (ROOT / 'patches/cudy-tr3600-v1-fixes.patch', 'hardware-fixes.patch')):
        shutil.copyfile(origin, OUT / name)
    with tarfile.open(OUT / 'same-build-packages.tar.gz', 'w:gz', compresslevel=1) as archive:
        for base in (SRC / 'bin/packages', TARGET / 'packages'):
            if base.exists():
                archive.add(base, arcname=str(base.relative_to(SRC / 'bin')))
    (OUT / 'UNVERIFIED.json').write_text(json.dumps({
        'state': 'Produced by compiler; feature and device verification still pending',
        'images': [path.name for path in images],
    }, indent=2) + '\n', encoding='utf-8')
    hashes = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            value = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    value.update(block)
            hashes.append(f'{value.hexdigest()}  {path.name}')
    (OUT / 'artifact-sha256sums').write_text('\n'.join(hashes) + '\n', encoding='utf-8')
    print('Raw firmware and matching package archive preserved for upload')
