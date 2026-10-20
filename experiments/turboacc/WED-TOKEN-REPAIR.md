The first physical MT7987/MT7992 WED test attached successfully, but wireless
authentication and packet delivery failed. Attachment is not a functional test.

The port imported MediaTek patch 0049's 16,384 hardware tokens while retaining
the old overlapping host allocation. The official 0054 patch, titled "add debug
tools", also contains essential production token ownership changes: hardware
IDs start at zero, host IDs start after the hardware pool, and the host pool has
15,360 entries. This functional subset is now included without the debug tools.

The common offload callback retains legacy upper-pool lending for other drivers.
TX allocation/release accounting is bounded by both ends of the hardware range,
so high host IDs are not incorrectly counted as hardware tokens. The total fits
the firmware's 15-bit TX token field. Initialization moves the host range only
after WED attachment succeeds; attachment failure retains the software path.

Reference: MediaTek mtk-openwrt-feeds commit
`c24f2ab0213a1356a4c9d6aade0142c32e44f1e1`,
`autobuild/unified/filogic/mac80211/25.12/files/package/kernel/mt76/patches/0054-mtk-mt76-add-debug-tools.patch`.

`test_wed_tokens.py` executes the actual patched C allocation/release and
offload callbacks, with kernel primitives supplied by a bounded test harness.
It covers full host allocation, exhaustion, hardware counter isolation,
enable/disable, management TX completion, and legacy hardware-token draining.

These checks and successful compilation do not establish physical forwarding.
Deployment still requires matching kernel ABI, recovery files, successful
authentication and DHCP on both radios, bidirectional traffic, and actual WED/PPE
activity with WED enabled. A failed test must preserve its diagnostics.
