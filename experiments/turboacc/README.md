# TR3600 acceleration port experiment

This branch contains paired source changes for Cudy TR3600 v1 / MT7987 and
the mt7996e-family wireless driver. Nothing here installs onto, reboots, or
flashes a running router. Build outputs are experimental and are not releases.

## What is being implemented

- MT7987 WED 3.1 support in the Ethernet/WED core, paired with matching mt76
  changes. MT7987 has a different hardware path from MT7988 and does not use
  the latter's WO firmware path. Changing only a module parameter is insufficient
  when that core implementation is absent.
- A real TurboACC backend for OpenWrt firewall4 and Netfilter flow tables.
  Software forwarding uses Netfilter flow offload; hardware forwarding uses
  the mainline MediaTek PPE driver. This is distinct from the vendor
  `kmod-mediatek_hnat` driver and is reported as such.
- The Broadcom-style UDP Full Cone NAT implementation from the pinned
  MT798x tree, adapted to Linux 6.12.94. It defaults to disabled. TCP and
  other protocols keep their existing NAT behavior. Existing tracked flows
  may retain their previous behavior until they expire.
- The original TurboACC frontend and five RPC methods, connected to actual
  kernel/firewall state. Unsupported vendor AP/PPE tuning controls are not
  advertised. A missing PPE or Full Cone backend causes an apply error.

`turboacc-control` validates configuration, checks the generated nftables
rules, applies the real fw4 rules and kernel sysctls, and restores the prior
configuration on failure. It preserves unrelated pending firewall edits.
Detailed apply errors are retained in `/tmp/turboacc-last-error`.
It does not modify LAN, DHCP, Wi-Fi, DNS, or host identity settings.

## Reproduce

Run the bounded **TR3600 acceleration backend compile probe** workflow on
this branch. It uses a standard public Ubuntu runner, with a 30 minute limit.
It uploads no artifacts or caches. The workflow records results in its log
and job summary.

The checks cover:

1. Pinned-source checksums and ARM64 compilation of NAT, WED and mt76.
2. Application of the complete pinned OpenWrt kernel patch stack, including
   the paired changes, source-package integration, and compilation of the
   combined Ethernet/PPE/WED code.
3. A minimal ARM64 kernel link followed by matching mac80211/mt76 module
   links with modpost checks. This validation configuration is not a router
   firmware image or a drop-in replacement for a running kernel.
4. An isolated QEMU VM running the modified Linux 6.12.94 kernel and actual
   OpenWrt UCI, netifd, firewall4 and nftables. Packet fixtures test ordinary
   NAT, UDP endpoint-independent mapping/filtering, TCP software flow offload,
   configuration rejection, failure rollback and the original RPC contract.

Only documentation address ranges are used in the VM. No personal settings,
router backups, keys or live network identifiers are build inputs.

To integrate into a separately prepared source tree at the exact pinned
OpenWrt version:

```sh
python3 experiments/turboacc/integrate_openwrt.py /path/to/openwrt
```

This installs the paired patches and source package, updates build selections,
and records their hashes. It refuses a mismatched kernel, mt76 or mac80211
version. Standard OpenWrt feeds/toolchain preparation is still required.
It does not build or deploy firmware by itself.

## Verification boundary

Object compilation does not establish a compatible replacement module for
an existing router kernel. The WED changes alter shared kernel/driver data
structures. A matched kernel and driver build is required for hardware tests.

QEMU can exercise NAT and software forwarding, but cannot emulate the TR3600
PPE/WED hardware. Physical WED attachment, DMA, Wi-Fi forwarding, throughput
and recovery remain unverified until a separately authorized controlled
hardware boot. A real hardware test must confirm successful attachment,
populated WED state and packet counters, PPE-bound flows and stable traffic;
the enable parameter alone is insufficient.

The original Full Cone implementation uses a conntrack helper. Its UDP flows
may be excluded from mainline flow offload; simultaneous TCP software offload
is tested separately. No claim is made that every Full Cone UDP flow is
hardware accelerated.

The intentionally omitted vendor-only features and affected source files
are listed in `port-scope.json`. Full production ABI/linking, hardware stability,
long-duration traffic and upgrade/recovery testing are additional work.

## Sources

Exact commits, versions and archive hashes are in `sources.json`.

- [OpenWrt](https://github.com/openwrt/openwrt)
- [OpenWrt mt76](https://github.com/openwrt/mt76)
- [MediaTek OpenWrt feeds](https://github.com/mediatek/mtk-openwrt-feeds)
- [Original MT798x TurboACC and Full Cone sources](https://github.com/padavanonly/immortalwrt-mt798x-6.6)

The original frontend and package code retain their GPL-3.0-only attribution;
kernel and mt76 changes retain their respective upstream license terms.
