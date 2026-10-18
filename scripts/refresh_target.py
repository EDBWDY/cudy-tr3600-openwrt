"""Refresh reviewed target-only inputs while retaining the authenticated compiler.

Compiler sources, host preparation, source pins, theme transforms and target
architecture must match exactly. This is an explicit continuation operation,
never a silent relaxation of checkpoint identity checks.
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys


def allowed_delta(previous, current):
    changed = sorted(name for name in previous.keys() | current.keys()
                     if previous.get(name) != current.get(name))
    for name in changed:
        if name.startswith(('package/', 'files/')) or name == 'config.seed':
            continue
        if name.startswith('experiments/turboacc/') and not name.endswith('sources.json'):
            continue
        raise RuntimeError('Compiler or unreviewed build input changed; refuse target-only reuse: ' + name)
    return changed


def refresh(root, metadata, changed):
    root = Path(root)
    source = root / 'openwrt'
    before = (source / '.config').read_text()
    sys.path.insert(0, str(root / 'experiments/turboacc'))
    from integrate_openwrt import integrate
    from refresh_customizations import configuration_values
    for package in (root / 'package').iterdir():
        shutil.copytree(package, source / 'package/custom' / package.name, dirs_exist_ok=True)
        for path in (source / 'package/custom' / package.name / 'files').rglob('*'):
            if path.is_file() and any(part in {'libexec', 'init.d', 'cgi-bin'} for part in path.parts):
                path.chmod(0o755)
    shutil.copytree(root / 'files', source / 'files', dirs_exist_ok=True)
    for path in (source / 'files/etc/uci-defaults').iterdir():
        path.chmod(0o755)
    shutil.copyfile(root / 'config.seed', source / '.config')
    integrate(source, replace_patches=True)
    subprocess.run(['make', 'defconfig'], cwd=source, check=True)
    old, new = configuration_values(before), configuration_values((source / '.config').read_text())
    config_delta = [key for key in old.keys() | new.keys() if old.get(key) != new.get(key)]
    if any(not key.startswith(('CONFIG_PACKAGE_', 'CONFIG_KERNEL_')) for key in config_delta):
        raise RuntimeError('Target architecture/compiler configuration changed; refuse compiler reuse')
    kernel_changed = any(name.endswith('.patch') for name in changed) or any(
        name.startswith('CONFIG_KERNEL_') for name in config_delta)
    targets = {'package/custom/luci-app-turboacc-mtk/clean'}
    for name in changed:
        if name.startswith('package/'):
            targets.add('package/custom/' + name.split('/')[1] + '/clean')
        if name.startswith('files/'):
            targets.add('package/base-files/clean')
    if kernel_changed:
        # The kernel build directory also contains external wireless/module
        # builds. Rebuild the paired target ABI, never reuse stale kmods.
        targets.add('target/linux/clean')
    subprocess.run(['make', *sorted(targets)], cwd=source, check=True)
    target = source / 'bin/targets/mediatek/filogic'
    for path in target.glob('*'):
        if path.is_file():
            path.unlink()  # Do not publish an old image if the new compile fails.
    if metadata['stage'] in {'rust', 'firmware'}:
        # Bounded actual dependency check must prove GCC and Rust remain usable.
        subprocess.run([sys.executable, root / 'scripts/check-toolchain-reuse.py'], check=True)
    (root / 'target-refresh.json').write_text(json.dumps({
        'changed_target_inputs': changed, 'kernel_rebuild_required': kernel_changed,
        'cleaned_target_directories': sorted(targets),
        'compiler_tree_preserved': True, 'old_images_removed': True,
    }, indent=2) + '\n')
