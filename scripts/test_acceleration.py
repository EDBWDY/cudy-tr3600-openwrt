"""Isolated UI and transaction checks; never writes router configuration."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AccelerationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_ui(self):
        subprocess.run(['node', 'scripts/test_acceleration_ui.cjs'], cwd=ROOT, check=True)

    @unittest.skipUnless(shutil.which('ucode'), 'ucode unavailable on this host')
    def test_transactions(self):
        source = (ROOT / 'package/luci-app-tr3600-acceleration/files/usr/share/tr3600-acceleration/engine.uc').read_text(encoding='utf-8')
        source = source[source.index('const MODULES'):source.index('\ntry {\n    let mode = ARGV[0]')]
        source = source.replace('let uci = cursor();', '')
        fixture = (ROOT / 'scripts/acceleration-transaction-fixture.uc').read_text(encoding='utf-8')
        subprocess.run(['ucode', '-'], input=fixture.replace('// ENGINE_INSERT', source), text=True, check=True)


if __name__ == '__main__':
    unittest.main()
