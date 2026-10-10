import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from image_extraction import extract_for_audit


@unittest.skipUnless(shutil.which('mksquashfs') and shutil.which('unsquashfs') and hasattr(os, 'geteuid'),
                     'Requires Linux SquashFS tools')
class AuditExtractionTests(unittest.TestCase):
    def test_console_node_does_not_require_root_and_regular_files_are_preserved(self):
        if os.geteuid() == 0:
            self.skipTest('Must exercise the unprivileged CI failure')
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / 'source'
            (source / 'dev').mkdir(parents=True)
            (source / 'required-plugin').write_text('audit sentinel')
            image = base / 'root.squashfs'
            subprocess.run(['mksquashfs', str(source), str(image), '-noappend', '-processors', '1',
                            '-p', 'dev/console c 0600 0 0 5 1'], check=True, capture_output=True)
            failed = subprocess.run(['unsquashfs', '-d', str(base / 'original'), str(image)], capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(b'console', failed.stderr)
            extract_for_audit('unsquashfs', image, base / 'fixed')
            self.assertEqual((base / 'fixed/required-plugin').read_text(), 'audit sentinel')
            self.assertFalse((base / 'fixed/dev/console').exists())

    def test_corrupt_image_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            image = base / 'corrupt.squashfs'
            image.write_bytes(b'not a valid SquashFS filesystem')
            with self.assertRaises(subprocess.CalledProcessError):
                extract_for_audit('unsquashfs', image, base / 'root')


if __name__ == '__main__':
    unittest.main()
