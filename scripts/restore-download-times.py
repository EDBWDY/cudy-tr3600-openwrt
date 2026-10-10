#!/usr/bin/env python3
"""Migrate old checkpoints AFTER successful OpenWrt checksum-checked download.

Old snapshots omitted download archives, although OpenWrt .prepared targets
depend on them. Downloads of the SAME locked source must not trigger a clean
rebuild just because their filesystem timestamps are newer than those targets.
New checkpoints preserve dl directly and never use this migration.
"""
import os
from pathlib import Path


def migrate(root):
    marker = root / 'legacy-downloads-missing'
    if not marker.is_file():
        print('Download archives preserved: no timestamp migration needed')
        return
    source = root / 'openwrt'
    stamps = [path for path in (source / 'build_dir').rglob('.prepared*') if path.is_file()]
    if not stamps:
        raise RuntimeError('Legacy checkpoint contains no prepared build stamps')
    # Earlier than EVERY existing prepared stamp, without changing any stamp,
    # source content, configuration, or patch. This prevents make's download
    # prerequisite from invalidating already-prepared identical sources.
    time_ns = min(path.stat().st_mtime_ns for path in stamps) - 1_000_000_000
    count = 0
    for path in (source / 'dl').rglob('*'):
        if path.is_file() and not path.is_symlink():
            os.utime(path, ns=(time_ns, time_ns))
            count += 1
    if not count:
        raise RuntimeError('Legacy archives have not been downloaded')
    marker.unlink()
    print(f'Migrated {count} checked archives; existing compile stamps retained')


if __name__ == '__main__':
    migrate(Path(__file__).resolve().parents[1])
