"""Reject private router state in build inputs and the extracted firmware."""
import json
import re
from pathlib import Path

SECRET_TEXT = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'tskey-(?:auth|api)-[A-Za-z0-9_-]{20,}'),
    re.compile(rb'(?:vmess|trojan|ss)://[A-Za-z0-9+/=_-]{24,}'),
    re.compile(rb'(?:ssh-ed25519|ssh-rsa) AAAA[A-Za-z0-9+/=]{24,}'),
]

def inspect_text(path):
    data = path.read_bytes()
    if any(pattern.search(data) for pattern in SECRET_TEXT):
        raise RuntimeError('Private credential material detected in ' + str(path))

def audit_source(root):
    overlay = root / 'files'
    names = {p.relative_to(overlay).as_posix() for p in overlay.rglob('*') if p.is_file()}
    if names != {'etc/uci-defaults/99-tr3600-custom'}:
        raise RuntimeError('Only the reviewed credential-free first-boot script may enter files/')
    count = 0
    for base in [overlay, root / 'package', root / 'platforms', root / 'optional']:
        for path in base.rglob('*'):
            if not path.is_file():
                continue
            if path.name in {'authorized_keys', 'shadow', 'passwd', 'identity.secret', 'tailscaled.state'} or path.suffix in {'.key', '.pem', '.bin', '.yaml', '.yml', '.apk'}:
                raise RuntimeError('Private state or unexpected binary input: ' + str(path))
            if path.is_symlink():
                raise RuntimeError('Unexpected source symlink: ' + str(path))
            if path.name == 'tr3600_clients' and re.search(r'^\s*config\s+client(?:\s|$)', path.read_text(), re.M):
                raise RuntimeError('Personal client aliases or MAC policies in source: ' + str(path))
            inspect_text(path)
            count += 1
    return {'result': 'No private overlay/configuration/credential inputs', 'source_files_checked': count}

def audit_image(rootfs):
    forbidden = ['etc/uhttpd.key', 'etc/tailscale/tailscaled.state',
                 'root/.ssh/authorized_keys', 'etc/dropbear/authorized_keys',
                 'etc/zerotier/identity.secret', 'var/lib/zerotier-one/identity.secret']
    for name in forbidden:
        if (rootfs / name).exists():
            raise RuntimeError('Private state embedded in firmware: ' + name)
    for pattern in ['etc/dropbear/*host_key', 'etc/tailscale/*.state',
                    'etc/openclash/config/*', 'etc/openclash/backup/*',
                    'etc/zerotier/networks.d/*', 'etc/tr3600-usb/*']:
        if any(p.is_file() for p in rootfs.glob(pattern)):
            raise RuntimeError('Personal state/configuration embedded: ' + pattern)
    clients = rootfs / 'etc/config/tr3600_clients'
    if clients.exists() and re.search(r'^\s*config\s+client(?:\s|$)', clients.read_text(), re.M):
        raise RuntimeError('Personal client aliases or MAC policies embedded in image')
    shadow = rootfs / 'etc/shadow'
    if shadow.exists():
        for line in shadow.read_text().splitlines():
            fields = line.split(':')
            # OpenWrt's default service accounts may use the one-byte x marker.
            if len(fields) > 1 and fields[1] not in {'', '*', '!', '!!', 'x'}:
                raise RuntimeError('Password or password hash embedded in etc/shadow')
    wireless = rootfs / 'etc/config/wireless'
    if wireless.exists() and re.search(r"option\s+(?:key|password)\s+['\"]?[^'\"\s]+", wireless.read_text()):
        raise RuntimeError('Wireless credential embedded in firmware')
    count = 0
    for folder in ['etc/config', 'etc/uci-defaults', 'root', 'etc/openclash',
                   'etc/tailscale', 'etc/zerotier']:
        for path in (rootfs / folder).rglob('*'):
            if path.is_file() and not path.is_symlink() and path.stat().st_size < 1024 * 1024:
                inspect_text(path)
                count += 1
    return {'result': 'No user credentials, subscriptions, VPN identities or private router state',
            'configuration_files_checked': count, 'shadow_has_no_password_hashes': True}

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(audit_source(root), indent=2))
