#!/usr/bin/env python3
"""Authenticated, streaming build checkpoints in Release assets, not Actions storage.

Only the OpenWrt compiler tree is archived. Git credential configuration and
runner home are excluded. Public source Git objects/refs/index remain intact
so restored package versions and build stamps do not drift. AES-GCM also
protects generated package-signing keys in the tree.
The key lives in an Actions secret, never in a public asset or build environment.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from checkpoint import recipe, digest

ROOT = Path(__file__).resolve().parents[1]
CHUNK = 128 * 1024 * 1024


def gh(*args, **kw):
    for attempt in range(3):
        try:
            return subprocess.run(['gh', *map(str, args)], check=True, **kw)
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def cipher():
    key = base64.b64decode(os.environ['CHECKPOINT_KEY'], validate=True)
    if len(key) != 32:
        raise RuntimeError('Checkpoint secret must encode exactly 32 bytes')
    return AESGCM(key)


def associated(metadata, index):
    return json.dumps({k: metadata[k] for k in
                       ('format', 'workspace', 'recipe', 'source_commit', 'stage',
                        'stage_complete', 'config_sha256', 'run_id')},
                      sort_keys=True).encode() + b':' + str(index).encode()


def create_release(tag, title):
    try:
        gh('release', 'create', tag, '--target', os.environ['GITHUB_SHA'],
           '--title', title, '--prerelease', '--notes',
           'Compiler checkpoint only. Not a firmware release or hardware validation.')
    except subprocess.CalledProcessError:
        # A successful create can be followed by a transient lost response.
        existing = subprocess.check_output(['gh', 'release', 'view', tag, '--json',
                                           'targetCommitish', '--jq', '.targetCommitish'], text=True).strip()
        if existing != os.environ['GITHUB_SHA']:
            raise RuntimeError('Existing checkpoint tag belongs to a different source')


def save(tag, stage):
    config = ROOT / 'openwrt/.config'
    if not config.is_file():
        raise RuntimeError('No configured compiler tree to preserve')
    status = ROOT / f'compile-{stage}.status'
    metadata = {
        'format': 'tr3600-release-aesgcm-zstd-v1', 'workspace': str(ROOT),
        'source_commit': os.environ['GITHUB_SHA'], 'recipe': recipe(ROOT),
        'stage': stage, 'stage_complete': status.is_file() and status.read_text().strip() == '0',
        'config_sha256': digest(config), 'parts': [],
        'run_id': os.environ['GITHUB_RUN_ID'],
        'download_archives_and_subsecond_timestamps_preserved': True,
    }
    aes = cipher()
    create_release(tag, f'TR3600 {stage} compiler checkpoint {metadata["run_id"]}')
    # Retain public source version metadata, but exclude credential-bearing
    # Git configs and hooks. Removing entire .git directories changes getver
    # and LuCI package version calculations after restore.
    tar = subprocess.Popen(['tar', '--format=posix', '--exclude=*/.git/config',
                            '--exclude=*/.git/config.worktree', '--exclude=*/.git/hooks',
                            '--exclude=.ssh', '--exclude=.aws', '--exclude=.codex',
                            '-cf', '-', '-C', str(ROOT), 'openwrt'], stdout=subprocess.PIPE)
    zstd = subprocess.Popen(['zstd', '-1', '-T2', '-c'], stdin=tar.stdout, stdout=subprocess.PIPE)
    tar.stdout.close()
    try:
        with tempfile.TemporaryDirectory(prefix='checkpoint-') as temporary:
            index = 0
            while True:
                # Buffered read fills this bounded chunk unless EOF occurs.
                data = zstd.stdout.read(CHUNK)
                if not data:
                    break
                nonce = os.urandom(12)
                encrypted = nonce + aes.encrypt(nonce, data, associated(metadata, index))
                name = f'compiler-{index:05d}.zst.aesgcm'
                path = Path(temporary) / name
                path.write_bytes(encrypted)
                gh('release', 'upload', tag, path, '--clobber')
                metadata['parts'].append({'name': name, 'bytes': len(encrypted),
                                          'sha256': hashlib.sha256(encrypted).hexdigest()})
                path.unlink()
                index += 1
                print(f'Encrypted compiler chunk {index} uploaded', flush=True)
            if zstd.wait() != 0 or tar.wait() != 0:
                raise RuntimeError('Checkpoint archive producer failed; no complete manifest published')
            manifest = Path(temporary) / 'checkpoint.json'
            manifest.write_text(json.dumps(metadata, indent=2) + '\n')
            # Publish the manifest last: an interrupted save is never restorable.
            gh('release', 'upload', tag, manifest, '--clobber')
    finally:
        if zstd.poll() is None:
            zstd.kill()
        if tar.poll() is None:
            tar.kill()
        zstd.stdout.close()
        zstd.wait()
        tar.wait()
    print(f'Complete checkpoint: {tag}; stage_complete={metadata["stage_complete"]}')


def restore(tag, next_stage, refresh_target=False):
    if (ROOT / 'openwrt').exists():
        raise RuntimeError('Refusing to overwrite an existing compiler tree')
    aes = cipher()
    with tempfile.TemporaryDirectory(prefix='checkpoint-') as temporary:
        folder = Path(temporary)
        gh('release', 'download', tag, '-p', 'checkpoint.json', '-D', folder, '--clobber')
        metadata = json.loads((folder / 'checkpoint.json').read_text())
        if metadata['format'] != 'tr3600-release-aesgcm-zstd-v1':
            raise RuntimeError('Unknown checkpoint format')
        if metadata['workspace'] != str(ROOT):
            raise RuntimeError('Compiler paths cannot be relocated')
        changed = []
        current = recipe(ROOT)
        if metadata['recipe'] != current:
            if not refresh_target or next_stage == 'verify':
                raise RuntimeError('Compiled source inputs differ; refusing unsafe checkpoint reuse')
            from refresh_target import allowed_delta
            changed = allowed_delta(metadata['recipe'], current)
        order = {'tools': 0, 'rust': 1, 'firmware': 2, 'verify': 3}
        prior, wanted = order[metadata['stage']], order[next_stage]
        if wanted < prior or wanted > prior + 1:
            raise RuntimeError('Checkpoint stage does not match requested continuation')
        if wanted > prior and not metadata['stage_complete'] and next_stage != 'verify':
            raise RuntimeError('Previous compiler stage is incomplete; resume that same stage')
        extract = subprocess.Popen(['tar', '--use-compress-program=zstd -d',
                                    '-xf', '-', '-C', str(ROOT)], stdin=subprocess.PIPE)
        try:
            for index, part in enumerate(metadata['parts']):
                expected = f'compiler-{index:05d}.zst.aesgcm'
                if part['name'] != expected or part['bytes'] > CHUNK + 28:
                    raise RuntimeError('Invalid checkpoint chunk manifest')
                path = folder / expected
                gh('release', 'download', tag, '-p', expected, '-D', folder, '--clobber')
                if path.stat().st_size != part['bytes'] or digest(path) != part['sha256']:
                    raise RuntimeError('Encrypted checkpoint chunk checksum mismatch')
                data = path.read_bytes()
                # GCM authentication finishes BEFORE any chunk is extracted.
                plain = aes.decrypt(data[:12], data[12:], associated(metadata, index))
                extract.stdin.write(plain)
                path.unlink()
            extract.stdin.close()
            if extract.wait() != 0:
                raise RuntimeError('Checkpoint extraction failed')
        finally:
            if not extract.stdin.closed:
                extract.stdin.close()
            if extract.poll() is None:
                extract.kill()
            extract.wait()
        if digest(ROOT / 'openwrt/.config') != metadata['config_sha256']:
            raise RuntimeError('Restored configuration does not match saved configuration')
        if changed:
            from refresh_target import refresh
            refresh(ROOT, metadata, changed)
    print('Authenticated compiler tree restored with timestamps and download archives')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['save', 'restore'])
    parser.add_argument('tag')
    parser.add_argument('stage', choices=['tools', 'rust', 'firmware', 'verify'])
    parser.add_argument('--refresh-target', action='store_true', help='Explicitly refresh only reviewed target inputs; preserve compiler')
    args = parser.parse_args()
    if args.operation == 'save':
        if args.refresh_target:
            parser.error('--refresh-target is only valid for restore')
        save(args.tag, args.stage)
    else:
        restore(args.tag, args.stage, args.refresh_target)
