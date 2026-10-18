"""Install the paired experimental WED/NAT/TurboACC sources into pinned OpenWrt.

This edits a compiler source tree only. It does not contact a router, enable
WED on a running system, flash an image, or claim hardware verification.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
from prepare_package import prepare

HERE=Path(__file__).resolve().parent
LOCK=json.loads((HERE/'sources.json').read_text())


def integrate(source, replace_patches=False):
    source=Path(source).resolve()
    if not (source/'target/linux/mediatek/dts/mt7987b-cudy-tr3600-v1.dts').is_file():
        raise RuntimeError('TR3600 board source is missing')
    if LOCK['kernel']['sha256'] not in (source/'target/linux/generic/kernel-6.12').read_text():
        raise RuntimeError('Kernel source version/hash differs')
    if LOCK['mt76_commit'] not in (source/'package/kernel/mt76/Makefile').read_text():
        raise RuntimeError('mt76 version differs')
    if 'PKG_VERSION:='+LOCK['backports']['version'] not in (source/'package/kernel/mac80211/Makefile').read_text():
        raise RuntimeError('mac80211 backports version differs')
    paths={
        'bcm-fullcone-6.12-experimental.patch':'target/linux/generic/hack-6.12/9998-tr3600-fullcone.patch',
        'mt7987-wed-kernel.patch':'target/linux/mediatek/patches-6.12/9998-tr3600-wed.patch',
        'mt7987-wed-mt76.patch':'package/kernel/mt76/patches/9998-tr3600-wed.patch',
    }
    for name,relative in paths.items():
        target=source/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_bytes()!=(HERE/name).read_bytes() and not replace_patches:raise RuntimeError('Refusing to overwrite a different patch: '+relative)
        shutil.copyfile(HERE/name,target)
    prepare(source/'package/custom/luci-app-turboacc-mtk')
    values={
        'CONFIG_TARGET_mediatek':'y','CONFIG_TARGET_mediatek_filogic':'y',
        'CONFIG_TARGET_mediatek_filogic_DEVICE_cudy_tr3600-v1':'y',
        'CONFIG_PACKAGE_luci':'y','CONFIG_PACKAGE_luci-app-turboacc-mtk':'y',
        'CONFIG_PACKAGE_kmod-nft-offload':'y','CONFIG_PACKAGE_kmod-nf-conntrack-netlink':'y',
        'CONFIG_PACKAGE_luci-app-tr3600-acceleration':'n',
    }
    cfg=source/'.config';text=cfg.read_text() if cfg.exists() else ''
    for name,value in values.items():
        text=re.sub(r'^(?:'+re.escape(name)+r'=.*|# '+re.escape(name)+r' is not set)\n?','',text,flags=re.M)
        text+=('# '+name+' is not set' if value=='n' else name+'='+value)+'\n'
    cfg.write_text(text)
    manifest={
        'kernel':LOCK['kernel']['version'],'mt76_commit':LOCK['mt76_commit'],
        'patches':{relative:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name,relative in paths.items()},
        'hardware_runtime_verified':False,
        'wed_parameter_for_later_controlled_hardware_test':'options mt7996e wed_enable=1',
        'live_router_changes':False,
    }
    (source/'acceleration-port-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    installed=source/'package/custom/luci-app-turboacc-mtk/root/usr/share/turboacc/port-manifest.json'
    installed.parent.mkdir(parents=True,exist_ok=True)
    installed.write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('openwrt_source');args=parser.parse_args()
    print(json.dumps(integrate(args.openwrt_source),indent=2))
