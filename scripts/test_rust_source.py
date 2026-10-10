import importlib.util
import tempfile
import unittest
from pathlib import Path

loader = importlib.util.spec_from_file_location('rust_source', Path(__file__).with_name('ensure-rust-source.py'))
module = importlib.util.module_from_spec(loader)
loader.loader.exec_module(module)


class RustArchiveTests(unittest.TestCase):
    config = ('PKG_VERSION:=1.96.0\nPKG_SOURCE:=rustc-$(PKG_VERSION)-src.tar.xz\n'
              'PKG_SOURCE_URL:=https://static.rust-lang.org/dist/\nPKG_HASH:=' + 'a' * 64 + '\n')

    def test_resolves_pinned_host_archive_before_make(self):
        name, url, value = module.spec(self.config)
        self.assertEqual(name, 'rustc-1.96.0-src.tar.xz')
        self.assertEqual(url, 'https://static.rust-lang.org/dist/' + name)
        self.assertEqual(value, 'a' * 64)

    def test_unexpected_archive_origin_fails(self):
        with self.assertRaises(RuntimeError):
            module.spec(self.config.replace('static.rust-lang.org', 'example.com'))

    def test_existing_corrupt_archive_is_not_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'rust.tar.xz'
            path.write_bytes(b'corrupt')
            with self.assertRaises(RuntimeError):
                module.verify(path, 'a' * 64)


if __name__ == '__main__':
    unittest.main()
