#!/usr/bin/env python3
"""Smoke-test actual encrypted Release upload/download before a long build.

Uses synthetic compiler files in a disposable hosted-runner job. The uniquely
named temporary Release is deleted afterwards; no real checkpoint is touched.
"""
import os
from pathlib import Path
import subprocess
import release_checkpoint as checkpoint

ROOT = Path(__file__).resolve().parents[1]
tag = f'transport-validation-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}'
tree = ROOT / 'openwrt'
if tree.exists():
    raise RuntimeError('Transport validation requires an empty disposable compiler workspace')
tree.mkdir()
(tree / '.config').write_text('CONFIG_TRANSPORT_FIXTURE=y\n')
(tree / 'stamp').write_bytes(os.urandom(65536))
os.utime(tree / 'stamp', ns=(1700000000123456789, 1700000000123456789))
(ROOT / 'compile-tools.status').write_text('0\n')
subprocess.run(['git', 'init', '-q', tree], check=True)
subprocess.run(['git', '-C', tree, '-c', 'user.name=Public fixture', '-c',
                'user.email=test@example.invalid', 'commit', '--allow-empty',
                '-qm', 'public source metadata fixture'], check=True)
head = subprocess.check_output(['git', '-C', tree, 'rev-parse', 'HEAD'])
try:
    checkpoint.save(tag, 'tools')
    original = ROOT / 'transport-original'
    tree.rename(original)
    checkpoint.restore(tag, 'rust')
    assert (tree / 'stamp').read_bytes() == (original / 'stamp').read_bytes()
    assert (tree / 'stamp').stat().st_mtime_ns == 1700000000123456789
    assert not (tree / '.git/config').exists()
    assert subprocess.check_output(['git', '-C', tree, 'rev-parse', 'HEAD']) == head
    print('REAL_RELEASE_CHECKPOINT_TRANSPORT_PASSED: authenticated upload/download, source version and timestamps preserved')
finally:
    subprocess.run(['gh', 'release', 'delete', tag, '--cleanup-tag', '--yes'], check=False)
