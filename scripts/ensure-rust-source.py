#!/usr/bin/env python3
"""Fetch the pinned host-only Rust archive before restoring download mtimes."""
import hashlib
import re
import urllib.request
from pathlib import Path


def spec(text):
    fields = {}
    for name in ('PKG_VERSION', 'PKG_SOURCE', 'PKG_SOURCE_URL', 'PKG_HASH'):
        matches = re.findall(r'^' + name + r':=(.+)$', text, re.M)
        if len(matches) != 1:
            raise RuntimeError(f'Unexpected pinned Rust field: {name}')
        fields[name] = matches[0].strip()
    version = fields['PKG_VERSION']
    filename = fields['PKG_SOURCE'].replace('$(PKG_VERSION)', version)
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or filename != f'rustc-{version}-src.tar.xz':
        raise RuntimeError('Unexpected Rust archive name')
    if fields['PKG_SOURCE_URL'] != 'https://static.rust-lang.org/dist/':
        raise RuntimeError('Unexpected Rust source origin')
    if not re.fullmatch(r'[a-f0-9]{64}', fields['PKG_HASH']):
        raise RuntimeError('Rust archive must have a pinned SHA256')
    return filename, fields['PKG_SOURCE_URL'] + filename, fields['PKG_HASH']


def verify(path, expected):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    if value.hexdigest() != expected:
        raise RuntimeError('Rust source checksum mismatch')


def main():
    root = Path(__file__).resolve().parents[1] / 'openwrt'
    name, url, expected = spec((root / 'feeds/packages/lang/rust/Makefile').read_text(encoding='utf-8'))
    archive = root / 'dl' / name
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        temporary = archive.with_suffix(archive.suffix + '.part')
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        verify(temporary, expected)
        temporary.replace(archive)
    verify(archive, expected)
    print(f'Host-only Rust source verified before timestamp migration: {name}')


if __name__ == '__main__':
    main()
