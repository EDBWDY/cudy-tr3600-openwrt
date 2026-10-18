"""Exercise real archive/encryption/restore with a fake Release transport."""
import base64
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from cryptography.exceptions import InvalidTag
import release_checkpoint as checkpoint


@unittest.skipUnless(sys.platform.startswith('linux'), 'GNU tar/zstd integration on Linux')
class ReleaseCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ('sources.json', 'config.seed', 'zerotier-config.openwrt.js'):
            (self.root / name).write_text('synthetic build input\n')
        self.tree = self.root / 'openwrt'
        self.tree.mkdir()
        for name, data in {
            '.config': b'CONFIG_TARGET_TEST=y\n',
            'staging_dir/toolchain-test/stamp/.gcc_final_installed': b'done',
            'build_dir/rust/.built': os.urandom(160000),
            'dl/pinned-source.tar.xz': b'pinned download',
            'key-build.pem': b'generated signing material must stay encrypted',
        }.items():
            path = self.tree / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        stamp = self.tree / 'build_dir/rust/.built'
        os.utime(stamp, ns=(1700000000123456789, 1700000000123456789))
        os.link(stamp, stamp.with_name('hardlink'))
        stamp.with_name('symlink').symlink_to('.built')
        self.original = stamp.read_bytes()
        (self.root / 'compile-tools.status').write_text('0\n')
        import subprocess
        subprocess.run(['git', 'init', '-q', self.tree], check=True)
        subprocess.run(['git', '-C', self.tree, '-c', 'user.name=Public fixture',
                        '-c', 'user.email=test@example.invalid', 'commit',
                        '--allow-empty', '-qm', 'public source metadata fixture'], check=True)
        self.source_head = subprocess.check_output(['git', '-C', self.tree, 'rev-parse', 'HEAD'])
        with (self.tree / '.git/config').open('a') as config:
            config.write('\n[http]\n extraheader = synthetic credential must not be archived\n')
        self.assets = {}
        for name, value in [('ROOT', self.root), ('CHUNK', 65536), ('gh', self.fake_gh)]:
            mocked = patch.object(checkpoint, name, value)
            mocked.start(); self.addCleanup(mocked.stop)
        environment = patch.dict(os.environ, {
            'CHECKPOINT_KEY': base64.b64encode(os.urandom(32)).decode(),
            'GITHUB_SHA': 'public-source-fixture', 'GITHUB_RUN_ID': 'fixture-run'})
        environment.start(); self.addCleanup(environment.stop)

    def fake_gh(self, *args, **kwargs):
        if args[:2] == ('release', 'upload'):
            path = Path(args[3]); self.assets[(args[2], path.name)] = path.read_bytes()
        elif args[:2] == ('release', 'download'):
            name = args[args.index('-p') + 1]
            folder = Path(args[args.index('-D') + 1])
            (folder / name).write_bytes(self.assets[(args[2], name)])
        elif args[:2] != ('release', 'create'):
            raise AssertionError(args)

    def test_encrypted_roundtrip_keeps_compiler_versions_and_key_but_excludes_git_credentials(self):
        checkpoint.save('test', 'tools')
        metadata = json.loads(self.assets[('test', 'checkpoint.json')])
        self.assertTrue(metadata['stage_complete'])
        self.assertGreater(len(metadata['parts']), 1)
        for part in metadata['parts']:
            self.assertNotIn(b'generated signing material', self.assets[('test', part['name'])])
        shutil.rmtree(self.tree)
        checkpoint.restore('test', 'rust')
        stamp = self.tree / 'build_dir/rust/.built'
        self.assertEqual(stamp.read_bytes(), self.original)
        self.assertEqual(stamp.stat().st_mtime_ns, 1700000000123456789)
        self.assertEqual(stamp.stat().st_ino, stamp.with_name('hardlink').stat().st_ino)
        self.assertTrue(stamp.with_name('symlink').is_symlink())
        self.assertTrue((self.tree / 'key-build.pem').is_file())
        self.assertFalse((self.tree / '.git/config').exists())
        import subprocess
        self.assertEqual(subprocess.check_output(['git', '-C', self.tree, 'rev-parse', 'HEAD']), self.source_head)

    def test_incomplete_tools_can_resume_tools_but_cannot_advance_to_rust(self):
        (self.root / 'compile-tools.status').write_text('124\n')
        checkpoint.save('partial', 'tools')
        shutil.rmtree(self.tree)
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            checkpoint.restore('partial', 'rust')
        checkpoint.restore('partial', 'tools')
        self.assertEqual((self.tree / 'build_dir/rust/.built').read_bytes(), self.original)

    def test_changed_ciphertext_is_rejected_before_extraction_even_with_changed_hash(self):
        checkpoint.save('test', 'tools')
        metadata = json.loads(self.assets[('test', 'checkpoint.json')])
        first = metadata['parts'][0]
        data = bytearray(self.assets[('test', first['name'])]); data[50] ^= 1
        self.assets[('test', first['name'])] = bytes(data)
        import hashlib
        first['sha256'] = hashlib.sha256(data).hexdigest()
        self.assets[('test', 'checkpoint.json')] = json.dumps(metadata).encode()
        shutil.rmtree(self.tree)
        with self.assertRaises(InvalidTag):
            checkpoint.restore('test', 'rust')
        self.assertFalse((self.tree / '.config').exists())
