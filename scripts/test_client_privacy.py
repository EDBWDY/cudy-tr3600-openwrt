import tempfile
import unittest
from pathlib import Path
from privacy_audit import audit_image


class ClientPrivacyTests(unittest.TestCase):
    def test_default_client_settings_are_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / 'etc/config/tr3600_clients'
            config.parent.mkdir(parents=True)
            config.write_text("config settings 'main'\n\toption interface 'lan'\n")
            audit_image(root)

    def test_saved_client_policy_cannot_enter_public_image(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / 'etc/config/tr3600_clients'
            config.parent.mkdir(parents=True)
            config.write_text("config client 'example'\n\toption alias 'Personal device'\n")
            with self.assertRaisesRegex(RuntimeError, 'Personal client'):
                audit_image(root)


if __name__ == '__main__':
    unittest.main()
