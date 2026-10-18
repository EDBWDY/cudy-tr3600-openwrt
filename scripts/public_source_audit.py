#!/usr/bin/env python3
"""Audit the complete public source snapshot without printing possible secrets."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from privacy_audit import audit_source, SECRET_TEXT

ROOT = Path(__file__).resolve().parents[1]


def audit(root=ROOT):
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others',
                                     '--exclude-standard', '-z'], cwd=root).decode().split('\0')
    patterns = {
        'account_token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})'),
        'personal_path': re.compile(rb'(?i)(?:[A-Z]:[/\\]U[s]ers[/\\]|[/]home[/](?!runner[/])[^/\s]+[/]|[/]U[s]ers[/][^/\s]+[/])'),
        'private_history_reference': re.compile(b'EDBWDY/' + b'cudy-' + b'tr3600-usb-custom'),
    }
    mac = re.compile(rb'(?i)(?<![0-9a-f:])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f:])')
    private_ip = re.compile(rb'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b')
    prohibited = {'authorized_keys', 'known_hosts', 'shadow', 'passwd', 'tailscaled.state',
                  'identity.secret', 'AdGuardHome.yaml'}
    hashes = {}
    for name in sorted(filter(None, paths)):
        path = root / name
        if path.is_symlink() or path.name in prohibited or any(p in {'.ssh', '.aws', 'Router_backup', '.codex'} for p in path.parts):
            raise RuntimeError('Private state path or symlink in public snapshot: ' + name)
        data = path.read_bytes()
        for label, pattern in patterns.items():
            if pattern.search(data):
                raise RuntimeError(label + ' detected in ' + name + '; matching text withheld')
        if any(pattern.search(data) for pattern in SECRET_TEXT):
            raise RuntimeError('Credential material detected in ' + name + '; matching text withheld')
        for value in mac.findall(data):
            allowed = value == b'00:00:00:00:00:00' or (
                path.name.startswith('test_') and value.lower().startswith(b'02:00:00:00:00:'))
            if not allowed:
                raise RuntimeError('Non-example device MAC in ' + name)
        for value in private_ip.findall(data):
            # OpenWrt's documented factory address is a product default.
            if value != b'192.168.1.1':
                raise RuntimeError('Private address other than documented factory default in ' + name)
        hashes[name] = hashlib.sha256(data).hexdigest()
    return {'scope': 'current public source snapshot; no private Git history imported',
            'files_checked': len(hashes), 'snapshot_sha256': hashlib.sha256(
                json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            'source_overlay': audit_source(root),
            'result': 'No account tokens, private keys, personal device identifiers, '
                      'subscriptions, VPN identities, backups or saved router configuration detected'}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
