import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('download_times', Path(__file__).with_name('restore-download-times.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LegacyCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'openwrt/dl/source.tar.xz'
        self.archive.parent.mkdir(parents=True)
        self.archive.write_bytes(b'same pinned source')
        self.stamp = self.root / 'openwrt/build_dir/host/rust/.prepared'
        self.stamp.parent.mkdir(parents=True)
        self.stamp.write_bytes(b'completed preparation')
        os.utime(self.stamp, ns=(1700000000123456789, 1700000000123456789))
        os.utime(self.archive, ns=(1800000000123456789, 1800000000123456789))

    def test_legacy_download_no_longer_invalidates_preparation(self):
        (self.root / 'legacy-downloads-missing').write_text('verified checkpoint')
        self.assertGreater(self.archive.stat().st_mtime_ns, self.stamp.stat().st_mtime_ns)
        original_stamp = self.stamp.stat().st_mtime_ns
        module.migrate(self.root)
        self.assertLess(self.archive.stat().st_mtime_ns, self.stamp.stat().st_mtime_ns)
        self.assertEqual(self.stamp.stat().st_mtime_ns, original_stamp)
        self.assertEqual(self.stamp.read_bytes(), b'completed preparation')
        self.assertEqual(self.archive.read_bytes(), b'same pinned source')
        self.assertFalse((self.root / 'legacy-downloads-missing').exists())

    def test_new_snapshot_archives_remain_untouched(self):
        original_time = self.archive.stat().st_mtime_ns
        module.migrate(self.root)
        self.assertEqual(self.archive.stat().st_mtime_ns, original_time)


if __name__ == '__main__':
    unittest.main()
