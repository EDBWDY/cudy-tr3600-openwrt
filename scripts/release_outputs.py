#!/usr/bin/env python3
"""Preserve compiler output before feature tests, independently of checkpoints."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def gh(*args):
    subprocess.run(['gh', *map(str, args)], check=True)


def publish(tag, folder, reports=False):
    paths = sorted(p for p in (ROOT / folder).glob('*') if p.is_file())
    if not paths:
        print('No output files available in ' + folder)
        return
    if any(p.stat().st_size >= 2 * 1024**3 for p in paths):
        raise RuntimeError('Release asset exceeds 2 GiB; split before publishing')
    if not reports:
        gh('release', 'create', tag, '--target', os.environ['GITHUB_SHA'], '--prerelease',
           '--title', 'TR3600 compiler output ' + os.environ['GITHUB_RUN_ID'], '--notes',
           'Compiler output saved before independent validation. Not flashed; '
           'WED physical forwarding and stability are not yet verified. See validation reports.')
    for path in paths:
        gh('release', 'upload', tag, path, '--clobber')
    if not reports:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('release=' + tag + '\n')
    print('Release output preserved: ' + tag)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('tag')
    parser.add_argument('folder')
    parser.add_argument('--reports', action='store_true')
    args = parser.parse_args()
    publish(args.tag, args.folder, args.reports)
