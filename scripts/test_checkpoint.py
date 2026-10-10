import copy
import tempfile
import os
import sys
import unittest
from pathlib import Path
from checkpoint import recipe, validate_metadata
import checkpoint


class CheckpointIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('sources.json', 'config.seed', 'scripts/prepare.py', 'zerotier-config.openwrt.js',
                     'package/fan/files/view.js', 'files/etc/uci-defaults/custom', 'patches/hardware.patch'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('original', encoding='utf-8')
        self.metadata = {'workspace': str(self.root.resolve()), 'recipe': recipe(self.root)}

    def test_matching_inputs_can_resume(self):
        validate_metadata(self.metadata, self.root)

    def test_changed_plugin_cannot_silently_reuse_old_tree(self):
        (self.root / 'package/fan/files/view.js').write_text('changed', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            validate_metadata(self.metadata, self.root)

    def test_missing_identity_entries_fail(self):
        incomplete = copy.deepcopy(self.metadata)
        incomplete['recipe'] = {}
        with self.assertRaises(RuntimeError):
            validate_metadata(incomplete, self.root)

    def test_different_absolute_workspace_fails(self):
        changed = copy.deepcopy(self.metadata)
        changed['workspace'] += '/other'
        with self.assertRaises(RuntimeError):
            validate_metadata(changed, self.root)

    def test_verifier_change_can_resume_without_recompiling(self):
        (self.root / 'scripts/verify.py').write_text('verification repair', encoding='utf-8')
        validate_metadata(self.metadata, self.root)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'GNU tar/pigz integration runs on build runner')
    def test_roundtrip_keeps_rust_work_stamps_links_and_nanosecond_times(self):
        original_root = checkpoint.ROOT
        checkpoint.ROOT = self.root
        self.addCleanup(setattr, checkpoint, 'ROOT', original_root)
        tree = self.root / 'openwrt'
        host = tree / 'build_dir/target-aarch64_cortex-a53_musl/host/rustc-test'
        host.mkdir(parents=True)
        (tree / '.config').write_text('CONFIG_TEST=y\n')
        downloaded = tree / 'dl/source.tar.xz'
        downloaded.parent.mkdir()
        downloaded.write_bytes(b'locked archive')
        os.utime(downloaded, ns=(1699999999123456789, 1699999999123456789))
        stamp = host / '.built'
        stamp.write_bytes(b'compiled object')
        os.utime(stamp, ns=(1700000000123456789, 1700000000123456789))
        os.link(stamp, host / 'hardlink')
        (host / 'symlink').symlink_to('.built')
        snapshot = self.root / 'checkpoint'
        checkpoint.save(snapshot)
        tree.rename(self.root / 'old-tree')
        checkpoint.restore(snapshot)
        self.assertEqual(stamp.read_bytes(), b'compiled object')
        self.assertEqual(stamp.stat().st_mtime_ns, 1700000000123456789)
        self.assertTrue((host / 'symlink').is_symlink())
        self.assertEqual(os.readlink(host / 'symlink'), '.built')
        self.assertEqual(stamp.stat().st_ino, (host / 'hardlink').stat().st_ino)
        self.assertEqual(downloaded.read_bytes(), b'locked archive')
        self.assertEqual(downloaded.stat().st_mtime_ns, 1699999999123456789)
        self.assertFalse((self.root / 'legacy-downloads-missing').exists())


if __name__ == '__main__':
    unittest.main()
