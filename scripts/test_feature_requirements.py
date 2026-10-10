"""Regression checks for package sub-options and dnsmasq feature evidence."""
import unittest
from feature_requirements import requested_packages, verify_dnsmasq_nftset


class FeatureRequirementsTest(unittest.TestCase):
    def test_suboption_is_checked_without_becoming_a_package(self):
        config = ('CONFIG_PACKAGE_dnsmasq-full=y\n'
                  'CONFIG_PACKAGE_dnsmasq_full_nftset=y\n'
                  'CONFIG_PACKAGE_kmod-usb-storage=y\n')
        packages, options = requested_packages(config, config)
        self.assertEqual(packages, ['dnsmasq-full', 'kmod-usb-storage'])
        self.assertEqual(options, {'dnsmasq_full_nftset': 'dnsmasq-full'})

    def test_dropped_suboption_still_fails(self):
        seed = 'CONFIG_PACKAGE_dnsmasq-full=y\nCONFIG_PACKAGE_dnsmasq_full_nftset=y\n'
        with self.assertRaises(RuntimeError):
            requested_packages(seed, 'CONFIG_PACKAGE_dnsmasq-full=y\n')

    def test_missing_owner_still_fails(self):
        config = 'CONFIG_PACKAGE_dnsmasq_full_nftset=y\n'
        with self.assertRaises(RuntimeError):
            requested_packages(config, config)

    def test_nftset_disabled_banner_is_rejected(self):
        banner = b'\0IPv6 DHCP DHCPv6 TFTP conntrack no-ipset no-nftset auth DNSSEC no-dumpfile\0'
        with self.assertRaises(RuntimeError):
            verify_dnsmasq_nftset(banner)

    def test_nftset_enabled_banner_is_accepted(self):
        banner = b'\0IPv6 DHCP DHCPv6 TFTP conntrack no-ipset nftset auth DNSSEC no-dumpfile\0'
        self.assertIn(' nftset ', verify_dnsmasq_nftset(banner))

    def test_ambiguous_banner_is_rejected(self):
        banner = b'\0DHCP conntrack ipset nftset auth DNSSEC dumpfile\0'
        with self.assertRaises(RuntimeError):
            verify_dnsmasq_nftset(banner + banner)


if __name__ == '__main__':
    unittest.main()
