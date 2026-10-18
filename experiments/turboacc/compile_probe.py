"""Compile and isolated-VM acceleration experiment. No router deployment.

Uses only pinned public sources. Object compilation checks C APIs, not the
running OpenWrt ABI, packet forwarding, NAT behaviour, or WED operation.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import shutil

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / 'sources.json').read_text())
BUILD = Path(tempfile.mkdtemp(prefix='tr3600-acceleration-', dir=os.environ.get('RUNNER_TEMP')))
RESULT = {'scope': LOCK['scope'], 'stages': {}, 'deployable': False,
          'physical_wed_runtime_verified': False, 'live_router_changes': False}


def download(url, path):
    request = urllib.request.Request(url, headers={'User-Agent': 'TR3600-public-acceleration-probe'})
    with urllib.request.urlopen(request, timeout=90) as source, path.open('wb') as target:
        while chunk := source.read(1024 * 1024):
            target.write(chunk)
    return path


def raw(repo, commit, path, target):
    return download(f'https://raw.githubusercontent.com/{repo}/{commit}/{path}', target)


def run(args, cwd):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def stage(name, callback):
    print('\nSTAGE:', name, flush=True)
    try:
        callback()
        RESULT['stages'][name] = 'passed'
    except Exception as error:
        RESULT['stages'][name] = f'failed: {error}'
        print(RESULT['stages'][name], flush=True)
    (HERE / 'result.json').write_text(json.dumps(RESULT, indent=2) + '\n')


def turboacc_syntax():
    root = 'package/mtk/applications/luci-app-turboacc-mtk/'
    for path, name, command in [
        ('root/etc/init.d/turboacc', 'turboacc-init', ['sh', '-n']),
        ('root/usr/libexec/rpcd/luci.turboacc', 'turboacc-rpc', ['luac5.1', '-p']),
        ('htdocs/luci-static/resources/view/turboacc.js', 'turboacc.js', ['node', '--check']),
    ]:
        target = raw(LOCK['turboacc_repository'], LOCK['turboacc_commit'], root + path, BUILD / name)
        run(command + [target], BUILD)


kernel = BUILD / ('linux-' + LOCK['kernel']['version'])


def prepare_kernel():
    archive = download(LOCK['kernel']['url'], BUILD / 'linux.tar.xz')
    actual = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
    if actual != LOCK['kernel']['sha256']:
        raise RuntimeError('Kernel source checksum mismatch')
    run(['tar', '-xf', archive], BUILD)
    run(['git', 'apply', '--check', HERE / 'bcm-fullcone-6.12-experimental.patch'], kernel)
    run(['git', 'apply', HERE / 'bcm-fullcone-6.12-experimental.patch'], kernel)
    # Apply the pinned OpenWrt changes that touch the WED core before checking
    # vendor patches. This avoids testing against an unrelated vanilla core.
    patches = [
        'generic/backport-6.12/731-v6.18-net-mediatek-wed-Introduce-MT7992-WED-support-to-MT7.patch',
        'generic/backport-6.12/732-v6.18-wifi-mt76-wed-use-proper-wed-reference-in-mt76-wed-d.patch',
        'generic/backport-6.12/733-v6.18-net-mtk-wed-add-dma-mask-limitation-and-GFP_DMA32-fo.patch',
        'mediatek/patches-6.12/940-net-ethernet-mtk_wed-rename-mtk_wed_get_memory_regio.patch',
        'mediatek/patches-6.12/942-net-ethernet-mtk_wed-move-cpuboot-in-a-dedicated-dts.patch',
        'mediatek/patches-6.12/943-net-ethernet-mtk_wed-move-ilm-a-dedicated-dts-node.patch',
        'mediatek/patches-6.12/944-net-ethernet-mtk_wed-move-dlm-a-dedicated-dts-node.patch',
    ]
    for index, path in enumerate(patches):
        patch = raw('openwrt/openwrt', LOCK['openwrt_commit'], 'target/linux/' + path, BUILD / f'wed-base-{index}.patch')
        run(['git', 'apply', '--check', patch], kernel)
        run(['git', 'apply', patch], kernel)
    run(['git', 'apply', '--check', HERE / 'mt7987-wed-kernel.patch'], kernel)
    run(['git', 'apply', HERE / 'mt7987-wed-kernel.patch'], kernel)
    run(['make', 'ARCH=arm64', 'CROSS_COMPILE=aarch64-linux-gnu-', 'defconfig'], kernel)
    run(['scripts/config', '--module', 'NF_CONNTRACK', '--module', 'NF_NAT',
         '--enable', 'NF_NAT_MASQUERADE', '--enable', 'NF_CONNTRACK_EVENTS',
         '--module', 'NF_CT_NETLINK', '--enable', 'NETFILTER_XTABLES',
         '--module', 'NETFILTER_XT_TARGET_MASQUERADE', '--module', 'NF_TABLES',
         '--module', 'NFT_MASQ', '--module', 'NFT_FLOW_OFFLOAD',
         '--module', 'NF_FLOW_TABLE', '--enable', 'ARCH_MEDIATEK',
         '--enable', 'NET_VENDOR_MEDIATEK', '--module', 'NET_MEDIATEK_SOC',
         '--module', 'MT7996E', '--enable', 'AVERAGE'], kernel)
    run(['make', 'ARCH=arm64', 'CROSS_COMPILE=aarch64-linux-gnu-', 'olddefconfig'], kernel)
    config = (kernel / '.config').read_text().splitlines()
    for required in ['CONFIG_NET_MEDIATEK_SOC=m', 'CONFIG_NET_MEDIATEK_SOC_WED=y',
                     'CONFIG_NF_CONNTRACK=m', 'CONFIG_NF_NAT=m']:
        if required not in config:
            raise RuntimeError('Compile harness dropped required configuration: ' + required)
    run(['make', '-j4', 'ARCH=arm64', 'CROSS_COMPILE=aarch64-linux-gnu-', 'prepare'], kernel)


def compile_nat():
    run(['make', '-j4', 'ARCH=arm64', 'CROSS_COMPILE=aarch64-linux-gnu-',
         'net/netfilter/nf_conntrack.o', 'net/netfilter/nf_nat.o',
         'net/netfilter/xt_MASQUERADE.o', 'net/netfilter/nft_masq.o',
         'net/netfilter/nft_flow_offload.o'], kernel)


def compile_wed_baseline():
    run(['make', '-j4', 'ARCH=arm64', 'CROSS_COMPILE=aarch64-linux-gnu-',
         'drivers/net/ethernet/mediatek/mtk_wed.o',
         'drivers/net/ethernet/mediatek/mtk_wed_wo.o',
         'drivers/net/ethernet/mediatek/mtk_wed_mcu.o',
         'drivers/net/ethernet/mediatek/mtk_wed_debugfs.o'], kernel)


def wed_kernel_dependency_check():
    path = '25.12/files/target/linux/mediatek/patches-6.12/999-wed-10-add-mt7987-hwpath-support.patch'
    patch = raw('mediatek/mtk-openwrt-feeds', LOCK['mediatek_commit'], path, BUILD / 'wed-mt7987.patch')
    run(['git', 'apply', '--check', patch], kernel)


def wed_mt76_dependency_check():
    archive = download('https://codeload.github.com/openwrt/mt76/tar.gz/' + LOCK['mt76_commit'], BUILD / 'mt76.tar.gz')
    run(['tar', '-xf', archive], BUILD)
    mt76 = BUILD / ('mt76-' + LOCK['mt76_commit'])
    run(['git', 'apply', '--check', HERE / 'mt7987-wed-mt76.patch'], mt76)
    run(['git', 'apply', HERE / 'mt7987-wed-mt76.patch'], mt76)
    bp_archive = download(LOCK['backports']['url'], BUILD / 'backports.tar.zst')
    if hashlib.file_digest(bp_archive.open('rb'), 'sha256').hexdigest() != LOCK['backports']['sha256']:
        raise RuntimeError('Backports checksum mismatch')
    run(['tar', '-xf', bp_archive], BUILD)
    bp = BUILD / ('backports-' + LOCK['backports']['version'])
    ow_archive = download('https://codeload.github.com/openwrt/openwrt/tar.gz/' + LOCK['openwrt_commit'], BUILD / 'openwrt.tar.gz')
    run(['tar', '-xf', ow_archive], BUILD)
    ow = BUILD / ('openwrt-' + LOCK['openwrt_commit'])
    for directory in ['build', 'subsys']:
        run(['sh', ow / 'scripts/patch-kernel.sh', bp, ow / 'package/kernel/mac80211/patches' / directory], BUILD)
    (bp / 'defconfig').write_text('CPTCFG_CFG80211=m\nCPTCFG_MAC80211=m\nCPTCFG_WLAN=y\n')
    flags = ['ARCH=arm64', 'CROSS_COMPILE=aarch64-linux-gnu-', 'KLIB_BUILD=' + str(kernel), 'KLIB=' + str(BUILD / 'unused-modules')]
    run(['make', *flags, 'usedefconfig'], bp)
    run(['make', *flags, 'backport-include/backport/autoconf.h'], bp)
    staged = BUILD / 'backport-headers'
    shutil.copytree(bp / 'backport-include', staged)
    (staged / 'linux/module.h').unlink(missing_ok=True)
    includes = f'-I{mt76} -I{staged}/uapi -I{staged} -I{bp}/include/uapi -I{bp}/include -include backport/autoconf.h -include backport/backport.h'
    run(['make', '-j4', '-C', kernel, 'ARCH=arm64', 'CROSS_COMPILE=aarch64-linux-gnu-',
         'M=' + str(mt76), 'CONFIG_MT76_CORE=m', 'CONFIG_MT76_CONNAC_LIB=m', 'CONFIG_MT7996E=m',
         'NOSTDINC_FLAGS=' + includes, 'mt76.o', 'mt76-connac-lib.o', 'mt7996/mt7996e.o'], BUILD)


def complete_openwrt_patch_stack():
    from integrate_openwrt import integrate
    ow = BUILD / ('openwrt-' + LOCK['openwrt_commit'])
    integrate(ow)
    tree=BUILD/'complete-target-kernel';tree.mkdir()
    run(['tar','-xf',BUILD/'linux.tar.xz','-C',tree,'--strip-components=1'],BUILD)
    for path in ['generic/files','mediatek/files','mediatek/files-6.12']:
        origin=ow/'target/linux'/path
        if origin.exists():shutil.copytree(origin,tree,dirs_exist_ok=True,symlinks=True)
    for path in ['generic/backport-6.12','generic/pending-6.12','generic/hack-6.12','mediatek/patches-6.12']:
        run(['sh',ow/'scripts/patch-kernel.sh',tree,ow/'target/linux'/path,'*.patch'],BUILD)
    for name in ['bcm-fullcone-6.12-experimental.patch','mt7987-wed-kernel.patch']:
        run(['git','apply','--reverse','--check',HERE/name],tree)
    shutil.copyfile(kernel/'.config',tree/'.config')
    flags=['ARCH=arm64','CROSS_COMPILE=aarch64-linux-gnu-']
    run(['make',*flags,'olddefconfig'],tree)
    run(['make','-j4',*flags,'prepare'],tree)
    run(['make','-j4',*flags,
         'drivers/net/ethernet/mediatek/mtk_eth_soc.o',
         'drivers/net/ethernet/mediatek/mtk_eth_path.o',
         'drivers/net/ethernet/mediatek/mtk_ppe.o',
         'drivers/net/ethernet/mediatek/mtk_ppe_offload.o',
         'drivers/net/ethernet/mediatek/mtk_wed.o',
         'drivers/net/ethernet/mediatek/mtk_wed_wo.o',
         'drivers/net/ethernet/mediatek/mtk_wed_mcu.o',
         'drivers/net/ethernet/mediatek/mtk_wed_debugfs.o',
         'net/netfilter/nf_conntrack.o','net/netfilter/nf_nat.o'],tree)


stage('upstream_turboacc_syntax_only', turboacc_syntax)
stage('prepare_6_12_94_source', prepare_kernel)
if RESULT['stages']['prepare_6_12_94_source'] == 'passed':
    stage('experimental_fullcone_and_nat_objects', compile_nat)
    stage('ported_mt7987_wed_objects', compile_wed_baseline)
    stage('ported_mt76_with_matching_backports', wed_mt76_dependency_check)
    stage('complete_openwrt_kernel_patch_stack_and_package_integration', complete_openwrt_patch_stack)
    from runtime_vm import verify_runtime
    stage('real_openwrt_fw4_fullcone_packet_tests_in_vm', lambda: verify_runtime(BUILD, download, run))
print(json.dumps(RESULT, indent=2), flush=True)
raise SystemExit(1 if any(value != 'passed' for value in RESULT['stages'].values()) else 0)
