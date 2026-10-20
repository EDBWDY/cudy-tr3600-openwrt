#!/usr/bin/env python3
"""Publish an already preserved and independently verified candidate atomically."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

IMAGE = 'openwrt-mediatek-filogic-cudy_tr3600-v1-squashfs-sysupgrade.bin'


def sha256(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def validate(folder, checkpoint, source):
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise RuntimeError('An exact source commit is required')
    if checkpoint.get('source_commit') != source or checkpoint.get('stage') != 'firmware' or not checkpoint.get('stage_complete'):
        raise RuntimeError('Candidate compiler checkpoint does not match the completed source build')
    status = json.loads((folder / 'validation-status.json').read_text())
    if status.get('image') != 'success' or status.get('source_tests') != 'success':
        raise RuntimeError('Independent validation has not passed')
    privacy = json.loads((folder / 'privacy-verification.json').read_text())
    if (privacy.get('image', {}).get('shadow_has_no_password_hashes') is not True
            or not privacy.get('image', {}).get('configuration_files_checked')
            or not privacy.get('source', {}).get('source_files_checked')):
        raise RuntimeError('Source and image privacy reports are required')
    verified = json.loads((folder / 'verification.json').read_text())
    if verified.get('board') != 'cudy,tr3600-v1' or sha256(folder / IMAGE) != verified.get('image_sha256'):
        raise RuntimeError('Published image differs from the independently verified image')
    recorded = set()
    for line in (folder / 'artifact-sha256sums').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if not re.fullmatch(r'[0-9a-f]{64}', digest) or '/' in name or '\\' in name or name in {'', '.', '..'}:
            raise RuntimeError('Unsafe compiler output manifest')
        if sha256(folder / name) != digest:
            raise RuntimeError('Compiler output checksum mismatch: ' + name)
        recorded.add(name)
    if not {IMAGE, 'same-build-packages.tar.gz', 'sha256sums'} <= recorded:
        raise RuntimeError('Compiler output manifest does not cover required artifacts')
    if not (folder / 'same-build-packages.tar.gz').is_file() or not (folder / 'sha256sums').is_file():
        raise RuntimeError('Matching packages and firmware checksums are required')
    return verified


def gh(*args, capture=False):
    result = subprocess.run(['gh', *map(str, args)], check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout if capture else None


def release_metadata(tag):
    # The tag endpoint omits drafts, even when `gh release view` finds them.
    # Resolve the draft's immutable release ID before checking uploaded assets.
    view = json.loads(gh('release', 'view', tag, '--json', 'apiUrl', capture=True))
    endpoint = view['apiUrl']
    expected = 'https://api.github.com/repos/' + os.environ['GH_REPO'] + '/releases/'
    if not endpoint.startswith(expected) or not endpoint[len(expected):].isdigit():
        raise RuntimeError('Unexpected release API identity')
    metadata = json.loads(gh('api', endpoint, capture=True))
    if metadata.get('tag_name') != tag:
        raise RuntimeError('Release API returned a different tag')
    return metadata


def publish(candidate, checkpoint_tag, tag):
    source = os.environ['GITHUB_SHA']
    repo = os.environ['GH_REPO']
    if not re.fullmatch(r'\d{4}\.\d{2}\.\d{2}(?:[.-][A-Za-z0-9.-]+)?', tag):
        raise RuntimeError('Use an explicit dated final release tag')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        folder, metadata = root / 'candidate', root / 'checkpoint'
        folder.mkdir(); metadata.mkdir()
        gh('release', 'download', candidate, '-D', folder)
        gh('release', 'download', checkpoint_tag, '-p', 'checkpoint.json', '-D', metadata)
        checkpoint = json.loads((metadata / 'checkpoint.json').read_text())
        verified = validate(folder, checkpoint, source)
        manifest_hash = sha256(folder / 'artifact-sha256sums')
        (folder / 'UNVERIFIED.json').unlink(missing_ok=True)
        (folder / 'artifact-sha256sums').unlink()
        provenance = {'source_commit': source, 'candidate_release': candidate,
            'checkpoint_release': checkpoint_tag, 'image_sha256': verified['image_sha256'],
            'compiler_output_manifest_sha256': manifest_hash,
            'independent_image_validation': 'success', 'source_tests': 'success',
            'privacy_validation': 'success',
            'published_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        (folder / 'final-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
        (folder / 'artifact-sha256sums').write_text(''.join(
            sha256(path) + '  ' + path.name + '\n' for path in sorted(folder.iterdir())
            if path.is_file() and path.name != 'artifact-sha256sums'))
        notes = root / 'release-notes.md'
        notes.write_text('适用于 Cudy TR3600 v1 / V1.0（R126）。\n\n'
            '- 配对的 WED 驱动修复与 MediaTek PPE / Netfilter 流量分载。\n'
            '- NAT 模式默认 MASQUERADE，受限锥形、全锥形及 TCP 覆盖需主动启用并确认风险。\n'
            '- 修复主题资源缓存、接口排版、Tailscale 手机表格和概览 USB 按钮对齐。\n'
            '- 包含客户端管理、网络身份、USB 管理、信道分析与常用插件。\n', encoding='utf-8')
        existing = subprocess.run(['gh', 'release', 'view', tag, '--json', 'isDraft,targetCommitish'],
                                  capture_output=True, text=True)
        if existing.returncode == 0:
            release = json.loads(existing.stdout)
            if not release['isDraft'] or release['targetCommitish'] != source:
                raise RuntimeError('Refusing to replace an existing published or unrelated final release')
        else:
            gh('release', 'create', tag, '--draft', '--target', source,
               '--title', 'TR3600 v1 · ' + tag + ' Final', '--notes-file', notes)
        paths = sorted(path for path in folder.iterdir() if path.is_file())
        for path in paths:
            gh('release', 'upload', tag, path, '--clobber')
        remote = release_metadata(tag)
        assets = {asset['name']: asset for asset in remote['assets']}
        for path in paths:
            asset = assets.get(path.name, {})
            if asset.get('size') != path.stat().st_size:
                raise RuntimeError('Final upload is incomplete: ' + path.name)
            if asset.get('digest') and asset['digest'] != 'sha256:' + sha256(path):
                raise RuntimeError('Final upload digest differs: ' + path.name)
        gh('release', 'edit', tag, '--draft=false', '--prerelease=false', '--latest')
        print(f'Final release published: https://github.com/{repo}/releases/tag/{tag}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate')
    parser.add_argument('checkpoint')
    parser.add_argument('tag')
    args = parser.parse_args()
    publish(args.candidate, args.checkpoint, args.tag)
