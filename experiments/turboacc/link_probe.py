"""Link a minimal ARM64 kernel and matching modules; never deploy them.

This catches unresolved symbols missed by individual object compilation.
The configuration is a validation fixture, not a production router image.
"""
from pathlib import Path
import shutil


def verify_links(build, lock, run):
    kernel=build/'complete-target-kernel'
    flags=['ARCH=arm64','CROSS_COMPILE=aarch64-linux-gnu-']
    run(['make',*flags,'mrproper'],kernel)
    run(['make',*flags,'tinyconfig'],kernel)
    features='MODULES MODULE_UNLOAD MODVERSIONS ARCH_MEDIATEK PCI OF NET INET IPV6 NETDEVICES ETHERNET NET_VENDOR_MEDIATEK NETFILTER NETFILTER_ADVANCED NETFILTER_INGRESS NF_NAT_MASQUERADE PROC_FS SYSCTL SYSFS DEBUG_FS WIRELESS WLAN RFKILL FW_LOADER AVERAGE RELAY BPF CRYPTO CRYPTO_AEAD CRYPTO_AES CRYPTO_CCM CRYPTO_GCM CRYPTO_CMAC CRYPTO_HMAC CRYPTO_SHA256 CRYPTO_SHA512 CRYPTO_MICHAEL_MIC CRYPTO_ECB CRYPTO_CBC CRYPTO_LIB_ARC4 CRYPTO_LIB_SHA1 CRYPTO_LIB_SHA256 CRC_CCITT CRC32 LIBCRC32C'.split()
    # OpenWrt pending patch 731 introduces this separate header/struct switch
    # so backports can be built without the in-tree cfg80211 module.
    features += ['CFG80211_HEADERS','NEW_LEDS','LEDS_CLASS','LEDS_TRIGGERS']
    config=['scripts/config']
    for feature in features:config+=['--enable',feature]
    for feature in ['NET_MEDIATEK_SOC','NF_CONNTRACK','NF_NAT','NF_CT_NETLINK','NF_TABLES','NFT_MASQ','NF_FLOW_TABLE','NFT_FLOW_OFFLOAD']:
        config+=['--module',feature]
    run(config,kernel)
    run(['make',*flags,'olddefconfig'],kernel)
    text=(kernel/'.config').read_text().splitlines()
    for required in ['CONFIG_NET_MEDIATEK_SOC=m','CONFIG_NET_MEDIATEK_SOC_WED=y','CONFIG_MODULES=y','CONFIG_NF_NAT=m','CONFIG_CFG80211_HEADERS=y']:
        if required not in text:raise RuntimeError('ARM64 link fixture dropped '+required)
    run(['make','-j4',*flags,'Image','modules'],kernel)
    bp=build/('backports-'+lock['backports']['version'])
    bp_flags=[*flags,'KLIB_BUILD='+str(kernel),'KLIB='+str(build/'unused-linked-modules')]
    run(['make',*bp_flags,'clean'],bp)
    run(['make',*bp_flags,'usedefconfig'],bp)
    run(['make','-j4',*bp_flags,'modules'],bp)
    for name in ['net/wireless/cfg80211.ko','net/mac80211/mac80211.ko']:
        if not (bp/name).is_file():raise RuntimeError('Backports module missing: '+name)
    mt76=build/('mt76-'+lock['mt76_commit'])
    run(['make','-C',kernel,*flags,'M='+str(mt76),'clean'],build)
    staged=build/'linked-backport-headers'
    shutil.copytree(bp/'backport-include',staged)
    (staged/'linux/module.h').unlink(missing_ok=True)
    includes=f'-I{mt76} -I{staged}/uapi -I{staged} -I{bp}/include/uapi -I{bp}/include -include backport/autoconf.h -include backport/backport.h'
    run(['make','-j4','-C',kernel,*flags,'M='+str(mt76),
         'CONFIG_MT76_CORE=m','CONFIG_MT76_CONNAC_LIB=m','CONFIG_MT7996E=m',
         'KBUILD_EXTRA_SYMBOLS='+str(bp/'Module.symvers'),
         'NOSTDINC_FLAGS='+includes,'modules'],build)
    for name in ['mt76.ko','mt76-connac-lib.ko','mt7996/mt7996e.ko']:
        if not (mt76/name).is_file():raise RuntimeError('Paired wireless module missing: '+name)
    print('ARM64_MATCHED_KERNEL_AND_MODULE_LINKS_PASSED',flush=True)
