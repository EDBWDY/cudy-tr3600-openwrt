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
        ('turboacc_safety.js','htdocs/luci-static/resources/turboacc_safety.js'),
    ]:
        target=destination/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(HERE/source,target);target.chmod(0o755)
    frontend=destination/'htdocs/luci-static/resources/view/turboacc.js'
    text=frontend.read_text()
    marker="'require view';"
    if text.count(marker)!=1:raise RuntimeError('Pinned TurboACC imports differ')
    text=text.replace(marker,marker+"\n'require turboacc_safety';")
    marker="\t\to.value('0', _('Disable'))\n\t\to.value('2', _('Boardcom_FULLCONE_NAT'));"
    if text.count(marker)!=1:raise RuntimeError('Pinned Full Cone option differs')
    text=text.replace(marker,marker+"\n\t\to.onchange = function(ev, section_id, value) {\n\t\t\tturboacc_safety.confirmFullCone(this, section_id, value);\n\t\t};")
    frontend.write_text(text)
    translations={
        'Full Cone NAT security warning':'全锥形 NAT 安全警告',
        'Enabling Full Cone NAT allows arbitrary external hosts to send packets through existing UDP mappings to internal devices. This increases exposure to unsolicited traffic and attacks. Enable it only when needed for games or P2P, and protect the internal devices.':'启用全锥形 NAT 后，外部任意主机可能通过已有的 UDP 映射向内网设备发送数据，增加被扫描或攻击的风险。请仅在确有游戏或 P2P 穿透需求时启用，并做好内网设备防护。',
        'The feature stays disabled until you confirm. Save and apply the configuration to activate it.':'确认前保持关闭；确认后还需保存并应用配置才会生效。',
        'Keep disabled':'保持关闭',
        'Understand the risk and continue':'了解风险，继续',
    }
    for relative,translated in [('po/zh_Hans/turboacc.po',True),('po/templates/turboacc.pot',False)]:
        path=destination/relative
        with path.open('a',encoding='utf-8') as output:
            for original,translation in translations.items():
                output.write('\nmsgid '+json.dumps(original,ensure_ascii=False)+'\nmsgstr '+json.dumps(translation if translated else '',ensure_ascii=False)+'\n')
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
