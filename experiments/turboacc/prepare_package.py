"""Assemble a pinned TurboACC package with real mainline fw4/PPE control."""
from pathlib import Path
import argparse
import json
import shutil
import urllib.request

HERE=Path(__file__).resolve().parent
LOCK=json.loads((HERE/'sources.json').read_text())


def prepare(destination):
    destination=Path(destination)
    root='package/mtk/applications/luci-app-turboacc-mtk/'
    paths=[
        'htdocs/luci-static/resources/view/turboacc.js',
        'po/zh_Hans/turboacc.po',
        'po/templates/turboacc.pot',
        'root/usr/share/luci/menu.d/luci-app-turboacc.json',
        'root/usr/share/rpcd/acl.d/luci-app-turboacc.json',
    ]
    for path in paths:
        url=f"https://raw.githubusercontent.com/{LOCK['turboacc_repository']}/{LOCK['turboacc_commit']}/{root}{path}"
        with urllib.request.urlopen(url,timeout=40) as source:
            target=destination/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read())
    for source,path in [
        ('turboacc-control','root/usr/libexec/turboacc-control'),
        ('turboacc.rpc','root/usr/libexec/rpcd/luci.turboacc'),
        ('turboacc.init','root/etc/init.d/turboacc'),
    ]:
        target=destination/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(HERE/source,target);target.chmod(0o755)
    target=destination/'root/etc/config/turboacc';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text("config turboacc 'config'\n option fastpath 'flow_offloading'\n option fastpath_fo_hw '1'\n option fullcone '0'\n option tcpcca 'cubic'\n")
    (destination/'Makefile').write_text('''# SPDX-License-Identifier: GPL-3.0-only
# Frontend: Copyright (C) 2018 Lean; Copyright (C) 2019-2022 ImmortalWrt.org
include $(TOPDIR)/rules.mk
PKG_LICENSE:=GPL-3.0-only
LUCI_TITLE:=TurboACC for mainline MediaTek PPE and Netfilter
LUCI_DEPENDS:=+firewall4 +nftables-json +jsonfilter +kmod-nft-offload
LUCI_PKGARCH:=all
include $(TOPDIR)/feeds/luci/luci.mk
''')
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination');args=parser.parse_args()
    print(prepare(args.destination))
