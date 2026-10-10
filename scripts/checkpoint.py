#!/usr/bin/env python3
"""Preserve a build tree, including timestamps, host-package builds and stamps."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def validate_metadata(metadata, root):
    if metadata['workspace'] != str(root.resolve()):
        raise RuntimeError('Checkpoint absolute workspace differs; toolchain paths cannot be relocated')
    if metadata['recipe'] != recipe(root):
        raise RuntimeError('Checkpoint compiled inputs differ from current recipe')


def recipe(root):
    paths = [root / name for name in ('sources.json', 'config.seed', 'scripts/prepare.py',
                                      'zerotier-config.openwrt.js')]
    for name in ('patches', 'package', 'files'):
        paths.extend(path for path in (root / name).rglob('*') if path.is_file())
    return {path.relative_to(root).as_posix(): digest(path) for path in sorted(paths)}


def save(folder):
    folder.mkdir(parents=True, exist_ok=False)
    archive = folder / 'openwrt.tar.gz'
    # GNU PAX preserves subsecond mtimes; plain checkout + partial cache did not.
    # Include ALL build_dir trees, staging_dir, source, feeds, .config and stamps.
    # Download archives MUST retain their mtimes: .prepared depends on them.
    subprocess.run(['tar', '--format=posix', '--use-compress-program=pigz -1 -p 2',
                    '-cf', str(archive), '-C', str(ROOT), 'openwrt'], check=True)
    metadata = {
        'workspace': str(ROOT.resolve()), 'archive_sha256': digest(archive),
        'run_id': os.environ.get('GITHUB_RUN_ID'),
        'head_sha': os.environ.get('GITHUB_SHA'),
        'recipe': recipe(ROOT),
        'config_sha256': digest(ROOT / 'openwrt/.config'),
        'download_archives_preserved': True,
    }
    (folder / 'checkpoint.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(f'Checkpoint saved: {archive.stat().st_size} bytes')


def restore(folder, refresh_customizations=False):
    metadata = json.loads((folder / 'checkpoint.json').read_text(encoding='utf-8'))
    if refresh_customizations:
        from refresh_customizations import validate_refresh
        validate_refresh(metadata, ROOT, recipe(ROOT))
    else:
        validate_metadata(metadata, ROOT)
    archive = folder / 'openwrt.tar.gz'
    if digest(archive) != metadata['archive_sha256']:
        raise RuntimeError('Checkpoint checksum mismatch')
    if (ROOT / 'openwrt').exists():
        raise RuntimeError('Refusing to overwrite existing build tree')
    subprocess.run(['tar', '--use-compress-program=pigz -d', '-xf', str(archive), '-C', str(ROOT)], check=True)
    if digest(ROOT / 'openwrt/.config') != metadata['config_sha256']:
        raise RuntimeError('Restored configuration differs')
    if not metadata.get('download_archives_preserved', False):
        # Only older checkpoints omitted dl. The workflow must first complete
        # pinned OpenWrt's checksum-checked `make download`, then fix timestamps.
        (ROOT / 'legacy-downloads-missing').write_text(metadata['archive_sha256'], encoding='utf-8')
    # Remove only the already-verified local copy to recover build disk space.
    archive.unlink()
    print('Full build tree restored with original paths and timestamps')
    if refresh_customizations:
        from refresh_customizations import refresh
        refresh(ROOT)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['save', 'restore'])
    parser.add_argument('folder', type=Path)
    parser.add_argument('--refresh-customizations', action='store_true')
    args = parser.parse_args()
    if args.operation == 'save':
        if args.refresh_customizations:
            parser.error('--refresh-customizations is only valid for restore')
        save(args.folder.resolve())
    else:
        restore(args.folder.resolve(), args.refresh_customizations)
