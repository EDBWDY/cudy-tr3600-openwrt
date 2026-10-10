import tempfile
import unittest
from pathlib import Path
from privacy_audit import audit_source, audit_image
from refresh_customizations import validate_refresh, validate_configuration
from checkpoint import recipe

ROOT = Path(__file__).resolve().parents[1]

class RefreshCompatibilityTests(unittest.TestCase):
    def test_identical_recipe_is_accepted_without_historical_commits(self):
        metadata = {'workspace': str(ROOT.resolve()), 'recipe': recipe(ROOT)}
        validate_refresh(metadata, ROOT, recipe(ROOT))

    def test_hardware_change_is_rejected_before_restoring_checkpoint(self):
        metadata = {'workspace': str(ROOT.resolve()), 'recipe': recipe(ROOT)}
        current = recipe(ROOT)
        current['sources.json'] = 'changed'
        with self.assertRaises(RuntimeError):
            validate_refresh(metadata, ROOT, current)

    def test_unrelated_package_and_toolchain_inputs_cannot_be_migrated(self):
        metadata = {'workspace': str(ROOT.resolve()), 'recipe': recipe(ROOT)}
        current = recipe(ROOT)
        current['package/tr3600-mihomo/Makefile'] = 'changed'
        with self.assertRaises(RuntimeError):
            validate_refresh(metadata, ROOT, current)

    def test_package_additions_do_not_require_a_compiler_rebuild(self):
        before = 'CONFIG_TARGET_mediatek=y\n# CONFIG_KERNEL_TEST is not set\nCONFIG_PACKAGE_luci=y\n'
        validate_configuration(before, before + 'CONFIG_PACKAGE_https-dns-proxy=y\n')

    def test_kernel_change_is_rejected(self):
        with self.assertRaises(RuntimeError):
            validate_configuration('CONFIG_KERNEL_TEST=y\n', '# CONFIG_KERNEL_TEST is not set\n')

class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_actual_inputs_are_clean(self):
        audit_source(ROOT)

    def test_wireless_config_cannot_be_imported_from_the_router(self):
        path = self.root / 'files/etc/config/wireless'
        path.parent.mkdir(parents=True)
        path.write_text('private configuration')
        with self.assertRaises(RuntimeError):
            audit_source(self.root)

    def test_blank_shadow_is_allowed_but_password_hash_is_rejected(self):
        path = self.root / 'etc/shadow'
        path.parent.mkdir(parents=True)
        path.write_text('root::0:0:99999:7:::\nnobody:*:0:0:99999:7:::\n')
        audit_image(self.root)
        path.write_text('root:$6$synthetic$fixture:0:0:99999:7:::\n')
        with self.assertRaises(RuntimeError):
            audit_image(self.root)

    def test_vpn_identity_is_rejected_even_without_a_known_token_format(self):
        path = self.root / 'etc/tailscale/tailscaled.state'
        path.parent.mkdir(parents=True)
        path.write_text('{}')
        with self.assertRaises(RuntimeError):
            audit_image(self.root)

    def test_proxy_subscription_cannot_enter_the_image(self):
        path = self.root / 'etc/openclash/config/private.yaml'
        path.parent.mkdir(parents=True)
        path.write_text('proxies: []')
        with self.assertRaises(RuntimeError):
            audit_image(self.root)

if __name__ == '__main__':
    unittest.main()
