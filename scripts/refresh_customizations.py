"""Refresh only reviewed user-space inputs on an authenticated old checkpoint."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from samba_labels import customize_package
from privacy_audit import audit_source
from mount_labels import customize_package as customize_mounts

def validate_refresh(metadata, root, current):
    if metadata['workspace'] != str(root.resolve()):
        raise RuntimeError('Checkpoint workspace differs; cannot relocate the toolchain')
    if metadata['recipe'] != current:
        raise RuntimeError('Checkpoint inputs differ; this snapshot only accepts an exact recipe match')


def configuration_values(text):
    values = {}
    for line in text.splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            key, value = line.split('=', 1)
            values[key] = value
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            values[line[2:-11]] = 'n'
    return values

def validate_configuration(before, after):
    old, new = configuration_values(before), configuration_values(after)
    changed = [key for key in old.keys() | new.keys()
               if not key.startswith('CONFIG_PACKAGE_') and old.get(key) != new.get(key)]
    if changed:
        raise RuntimeError('Non-package configuration changed; refusing toolchain reuse: ' + str(changed))

def refresh(root):
    audit_source(root)
    src = root / 'openwrt'
    before = (src / '.config').read_text()
    for package in (root / 'package').iterdir():
        shutil.copytree(package, src / 'package/custom' / package.name, dirs_exist_ok=True)
    shutil.copytree(root / 'files', src / 'files', dirs_exist_ok=True)
    for path in (src / 'files/etc/uci-defaults').iterdir():
        path.chmod(0o755)
    for package in ['luci-app-tr3600-fan', 'luci-app-tr3600-usb', 'luci-app-tr3600-clients']:
        for path in (src / 'package/custom' / package / 'files').rglob('*'):
            if path.is_file() and ('init.d' in path.parts or 'libexec' in path.parts):
                path.chmod(0o755)
    customize_package(src / 'feeds/luci/applications/luci-app-samba4')
    customize_mounts(src / 'feeds/luci/modules/luci-mod-system')
    shutil.copyfile(root / 'config.seed', src / '.config')
    subprocess.run(['make', 'defconfig'], cwd=src, check=True)
    after = (src / '.config').read_text()
    validate_configuration(before, after)
    missing = [line for line in (root / 'config.seed').read_text().splitlines()
               if line.startswith('CONFIG_') and line.endswith('=y') and line not in after.splitlines()]
    if missing:
        raise RuntimeError('Refreshed configuration lost required features: ' + str(missing))
    (root / 'customizations-refresh.json').write_text(json.dumps({
        'checkpoint_policy': 'exact_recipe',
        'result': 'Custom packages and defaults updated; non-package build settings unchanged',
        'new_packages': [],
    }, indent=2) + '\n')
