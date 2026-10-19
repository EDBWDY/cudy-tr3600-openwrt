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
  MT798x tree, adapted to Linux 6.12.94, with an additional address-restricted
  cone mode. The default is system NAT. TCP requires an additional, disabled
  by default opt-in and the paired kernel implementation in this branch.
  IPv6 and other protocols retain their existing NAT behavior.
- The original TR3600 card frontend, NAT mode and congestion controls, and
  the TurboACC RPC contract, connected to actual
  kernel/firewall state. Unsupported vendor AP/PPE tuning controls are not
  advertised. A missing PPE or Full Cone backend causes an apply error.

`turboacc-control` validates configuration, checks the generated nftables
rules, applies the real fw4 rules and kernel sysctls, and restores the prior
configuration on failure. It preserves unrelated pending firewall edits.
Detailed apply errors are retained in `/tmp/turboacc-last-error`.
It does not modify LAN, DHCP, Wi-Fi, DNS, or host identity settings.

The three modes are `0` system default NAT, `1` address-restricted cone (an
already-contacted external IP may send from a different source port), and
`2` full cone (any external IP/port may use an existing mapping).
The two cone modes apply to IPv4 UDP, with optional IPv4 TCP support controlled
by `fullcone_tcp`. The base `fullcone_protocol` remains `udp`; setting it to
`tcp` is rejected, so UDP-only configurations keep their original semantics.
TCP is offered only when `/proc/sys/net/netfilter/nf_conntrack_nat_tcp` exists.

Cone support is compiled in but defaults to disabled in both the kernel and
the package configuration. Selecting a cone mode in LuCI opens a security
warning before applying an enabled mode or changing its TCP scope. Canceling
keeps the running configuration unchanged; confirmation applies the requested
settings through the same transactional controller.

Mode changes clear existing IPv4 UDP connection state, including wildcard
expectations and already-related inbound child flows. UDP applications may
briefly reconnect. This prevents an old full-cone mapping from staying open
after selecting restricted or default NAT. UDP-only changes preserve TCP/IPv6.
When TCP cone NAT is disabled or its mode changes, a kernel setter removes
only its own helper masters and RELATED children, including their expectations.
Ordinary TCP sessions and local management connections are preserved. Newly
created TCP cone mappings are limited to forwarded traffic, not router-local
outbound connections. The TCP flag is per network namespace and starts at zero.

The card UI preserves pending edits and open dropdowns during polling. It lists
only congestion algorithms reported by the current kernel. Congestion control
applies to TCP terminated by the router; it does not replace client TCP stacks.

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
   NAT, restricted/full cone mapping and filtering, two-client port collisions,
   live-socket restoration of default NAT, a TCP connection surviving UDP-only
   mode changes, TCP cone handshakes and payloads, opt-out cleanup, software
   flow offload, configuration rejection, failure
   rollback and the original RPC contract. A separate test uses the actual
   pinned LuCI class runtime to exercise enable/cancel/dismiss confirmation.

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
The new TCP flag also changes conntrack namespace layout. Do not hot-swap
these NAT/conntrack modules into the previously released kernel.

QEMU can exercise NAT and software forwarding, but cannot emulate the TR3600
PPE/WED hardware. Physical WED attachment, DMA, Wi-Fi forwarding, throughput
and recovery remain unverified until a separately authorized controlled
hardware boot. A real hardware test must confirm successful attachment,
populated WED state and packet counters, PPE-bound flows and stable traffic;
the enable parameter alone is insufficient.

The cone implementation uses conntrack helpers. Its UDP and opt-in TCP flows
may be excluded from mainline flow offload; simultaneous ordinary TCP software
offload is tested separately. No claim is made that cone flows are hardware
accelerated.

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
