"""Distinguish selected packages from their build options and inspect features."""
import re

# This symbol is a bool inside Package/dnsmasq-full/config in the pinned source.
PACKAGE_OPTIONS = {'dnsmasq_full_nftset': 'dnsmasq-full'}


def requested_packages(seed, configuration):
    selected = [line for line in seed.splitlines()
                if line.startswith('CONFIG_') and line.endswith('=y')]
    missing = set(selected) - set(configuration.splitlines())
    if missing:
        raise RuntimeError(f'Requested build settings missing: {sorted(missing)}')
    names = [line.removeprefix('CONFIG_PACKAGE_').removesuffix('=y')
             for line in selected if line.startswith('CONFIG_PACKAGE_')]
    options = {name: PACKAGE_OPTIONS[name] for name in names if name in PACKAGE_OPTIONS}
    packages = [name for name in names if name not in PACKAGE_OPTIONS]
    for option, owner in options.items():
        if owner not in packages:
            raise RuntimeError(f'Build option {option} requires selected package {owner}')
    return packages, options


def verify_dnsmasq_nftset(binary):
    # dnsmasq 2.93 src/config.h builds one compile-options string, with
    # "no-nftset" when HAVE_NFTSET is absent. Inspect that string without
    # executing the router's binary on the build host.
    banners = [value for value in re.findall(rb'[\x20-\x7e]{8,}', binary)
               if b'conntrack ' in value and b'nftset ' in value
               and b'DNSSEC ' in value and b'dumpfile' in value]
    if len(banners) != 1 or b'nftset' not in banners[0].split():
        raise RuntimeError('Installed dnsmasq lacks a unique nftset-enabled compile-options banner')
    return banners[0].decode('ascii')
