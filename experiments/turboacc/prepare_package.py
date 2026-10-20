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
        ('turboacc-ui','root/usr/libexec/turboacc-ui'),
        ('turboacc-wed','root/usr/libexec/turboacc-wed'),
        ('turboacc.rpc','root/usr/libexec/rpcd/luci.turboacc'),
        ('turboacc.init','root/etc/init.d/turboacc'),
        ('turboacc_safety.js','htdocs/luci-static/resources/turboacc_safety.js'),
        ('turboacc_wed.js','htdocs/luci-static/resources/turboacc_wed.js'),
    ]:
        target=destination/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(HERE/source,target);target.chmod(0o755)
    frontend=destination/'htdocs/luci-static/resources/view/turboacc.js'
    text=frontend.read_text()
    marker="'require view';"
    if text.count(marker)!=1:raise RuntimeError('Pinned TurboACC imports differ')
    text=text.replace(marker,marker+"\n'require turboacc_safety';\n'require turboacc_wed';")
    if text.count('return m.render();') != 1:raise RuntimeError('Pinned TurboACC rendering changed')
    text=text.replace('return m.render();','return turboacc_wed.render(m);')
    text=text.replace("_('Flow offloading')", "_('Netfilter flow offload')")
    # The vendor driver controls have no corresponding mainline implementation.
    # Remove those options, instead of leaving misleading settings in the UI.
    start=text.index("\t\to = s.option(form.Flag, 'fastpath_mh_eth_hnat',")
    end=text.index("\t\to = s.option(form.ListValue, 'fullcone',",start)
    text=text[:start]+text[end:]
    text=text.replace('Requires hardware NAT support. Implemented at least for mt7621.',
                      'MediaTek PPE hardware flow offload for eligible routed Ethernet traffic. WED additionally connects supported Wi-Fi traffic to PPE. Proxy and locally terminated traffic may not be offloaded.')
    marker="\t\to.value('0', _('Disable'))\n\t\to.value('2', _('Boardcom_FULLCONE_NAT'));"
    if text.count(marker)!=1:raise RuntimeError('Pinned Full Cone option differs')
    choices="\t\to.value('0', _('System default NAT'));\n\t\to.value('1', _('Address-restricted cone NAT (UDP)'));\n\t\to.value('2', _('Full Cone NAT (UDP)'));"
    text=text.replace(marker,choices+"\n\t\to.onchange = function(ev, section_id, value) {\n\t\t\tturboacc_safety.confirmConeNat(this, section_id, value);\n\t\t};")
    old_description="Full cone NAT (NAT1) can improve gaming performance effectively."
    description='These modes apply to IPv4 UDP only. TCP and other protocols keep system default NAT. Changing the mode clears existing IPv4 UDP state and may briefly reconnect UDP applications.'
    if text.count(old_description)!=1:raise RuntimeError('Pinned cone NAT description differs')
    text=text.replace(old_description,description)
    text=text.replace("_('Full Cone NAT')","_('UDP NAT mode')").replace("_('Full cone NAT')","_('UDP NAT mode')")
    frontend.write_text(text)
    # Reuse the original TR3600 card design; keep one actual TurboACC backend.
    shutil.copyfile(HERE/'turboacc_cards.js',frontend)
    shutil.copyfile(HERE/'turboacc_cards.js',destination/'htdocs/luci-static/resources/view/turboacc_cards_v5.js')
    shutil.copyfile(HERE/'turboacc_cards.css',destination/'htdocs/luci-static/resources/turboacc_cards_v3.css')
    translations={
        'Network acceleration':'网络加速',
        'Netfilter flow offload':'Netfilter 软件流量分载',
        'WED wireless acceleration':'WED 无线加速',
        'Enable WED at next boot':'下次启动启用 WED',
        'WED device attached; physical throughput is not measured here':'WED 设备已附加；此处不代表已测得硬件吞吐',
        'WED is disabled':'WED 已关闭',
        'The mt7996e WED parameter is unavailable':'mt7996e 的 WED 参数不可用',
        'WED was requested, but no wireless device attached':'已请求启用 WED，但没有无线设备成功附加',
        'WED initialization failed; see the error log':'WED 初始化失败，请查看错误日志',
        'WED status unavailable':'WED 状态不可用',
        'A reboot is required to apply the saved WED setting':'已保存的 WED 设置需重启后生效',
        'No WED kernel messages':'暂无 WED 内核日志',
        'WED error log':'WED 错误日志',
        'Uses the paired MediaTek WED and mt76 driver. Saving never reloads Wi-Fi or reboots the router. Hardware forwarding still requires a controlled device test.':'使用配套的 MediaTek WED 与 mt76 驱动。保存不会重载 Wi-Fi 或重启路由器；硬件转发仍需受控实机验证。',
        'MediaTek PPE hardware flow offload for eligible routed Ethernet traffic. WED additionally connects supported Wi-Fi traffic to PPE. Proxy and locally terminated traffic may not be offloaded.':'MediaTek PPE 可分载符合条件的以太网路由流量；WED 将支持的 Wi-Fi 流量接入 PPE。代理及由本机终止的连接可能无法分载。',
        'System default NAT':'系统默认 NAT',
        'UDP NAT mode':'UDP NAT 模式',
        'Address-restricted cone NAT (UDP)':'受限锥形 NAT（按来源 IP，UDP）',
        'Full Cone NAT (UDP)':'全锥形 NAT（UDP）',
        'UDP cone NAT security warning':'UDP 锥形 NAT 安全警告',
        'Enabling Full Cone NAT allows arbitrary external hosts to send packets through existing UDP mappings to internal devices. This increases exposure to unsolicited traffic and attacks. Enable it only when needed for games or P2P, and protect the internal devices.':'启用全锥形 NAT 后，外部任意主机可能通过已有的 UDP 映射向内网设备发送数据，增加被扫描或攻击的风险。请仅在确有游戏或 P2P 穿透需求时启用，并做好内网设备防护。',
        'The feature stays disabled until you confirm. Save and apply the configuration to activate it.':'确认前保持关闭；确认后还需保存并应用配置才会生效。',
        'Address-restricted cone NAT allows previously contacted external IP addresses to send packets from any source port through existing UDP mappings. This is less restrictive than the system default NAT. Enable it only when needed.':'受限锥形 NAT 允许已联系过的外部 IP 从任意来源端口通过已有 UDP 映射发送数据，限制弱于系统默认 NAT，请仅在确有需要时启用。',
        description:'这些模式仅作用于 IPv4 UDP；TCP 和其他协议保持系统默认 NAT。切换模式会清理已有 IPv4 UDP 连接，相关应用可能短暂重连。',
        'Keep disabled':'保持关闭',
        'Understand the risk and continue':'了解风险，继续',
    }
    for relative,translated in [('po/zh_Hans/turboacc.po',True),('po/templates/turboacc.pot',False)]:
        path=destination/relative
        with path.open('a',encoding='utf-8') as output:
            for original,translation in translations.items():
                output.write('\nmsgid '+json.dumps(original,ensure_ascii=False)+'\nmsgstr '+json.dumps(translation if translated else '',ensure_ascii=False)+'\n')
    target=destination/'root/etc/config/turboacc';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text("config turboacc 'config'\n option fastpath 'flow_offloading'\n option fastpath_fo_hw '1'\n option fullcone '0'\n option fullcone_protocol 'udp'\n option fullcone_tcp '0'\n option wed_enable '0'\n option tcpcca 'cubic'\n")
    acl=destination/'root/usr/share/rpcd/acl.d/luci-app-turboacc.json'
    values=json.loads(acl.read_text())
    values['luci-app-turboacc']['read']['ubus']['luci.turboacc'].extend(['getWedStat','getUiStatus'])
    values['luci-app-turboacc'].setdefault('write',{}).setdefault('ubus',{}).setdefault('luci.turboacc',[]).append('saveUiSettings')
    acl.write_text(json.dumps(values,indent=2)+'\n')
    menu=destination/'root/usr/share/luci/menu.d/luci-app-turboacc.json'
    values=json.loads(menu.read_text());values['admin/network/turboacc']['title']='Network acceleration'
    values['admin/network/turboacc']['action']['path']='turboacc_cards_v5'
    menu.write_text(json.dumps(values,indent=2)+'\n')
    (destination/'Makefile').write_text('''# SPDX-License-Identifier: GPL-3.0-only
# Frontend: Copyright (C) 2018 Lean; Copyright (C) 2019-2022 ImmortalWrt.org
include $(TOPDIR)/rules.mk
PKG_NAME:=luci-app-turboacc-mtk
LUCI_NAME:=luci-app-turboacc-mtk
PKG_LICENSE:=GPL-3.0-only
LUCI_TITLE:=TurboACC for mainline MediaTek PPE and Netfilter
LUCI_DEPENDS:=+firewall4 +nftables-json +jsonfilter +conntrack +kmod-nft-offload +kmod-nf-conntrack-netlink
LUCI_PKGARCH:=all
include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
''')
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination');args=parser.parse_args()
    print(prepare(args.destination))
