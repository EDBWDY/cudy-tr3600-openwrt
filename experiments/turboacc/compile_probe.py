"""Compile-only acceleration experiment. Never install the output on a router.

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

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / 'sources.json').read_text())
BUILD = Path(tempfile.mkdtemp(prefix='tr3600-acceleration-', dir=os.environ.get('RUNNER_TEMP')))
RESULT = {'scope': LOCK['scope'], 'stages': {}, 'deployable': False}


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
    run(['make', 'ARCH=arm64', 'CROSS_COMPILE=aarch64-linux-gnu-', 'defconfig'], kernel)
    run(['scripts/config', '--module', 'NF_CONNTRACK', '--module', 'NF_NAT',
         '--enable', 'NF_NAT_MASQUERADE', '--enable', 'NF_CONNTRACK_EVENTS',
         '--module', 'NF_CT_NETLINK', '--enable', 'NETFILTER_XTABLES',
         '--module', 'NETFILTER_XT_TARGET_MASQUERADE', '--module', 'NF_TABLES',
         '--module', 'NFT_MASQ', '--module', 'NFT_FLOW_OFFLOAD',
         '--module', 'NF_FLOW_TABLE', '--enable', 'ARCH_MEDIATEK',
         '--enable', 'NET_VENDOR_MEDIATEK', '--module', 'NET_MEDIATEK_SOC'], kernel)
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
         'drivers/net/ethernet/mediatek/mtk_wed_wo.o'], kernel)


def wed_kernel_dependency_check():
    path = '25.12/files/target/linux/mediatek/patches-6.12/999-wed-10-add-mt7987-hwpath-support.patch'
    patch = raw('mediatek/mtk-openwrt-feeds', LOCK['mediatek_commit'], path, BUILD / 'wed-mt7987.patch')
    run(['git', 'apply', '--check', patch], kernel)


def wed_mt76_dependency_check():
    archive = download('https://codeload.github.com/openwrt/mt76/tar.gz/' + LOCK['mt76_commit'], BUILD / 'mt76.tar.gz')
    run(['tar', '-xf', archive], BUILD)
    path = 'autobuild/unified/filogic/mac80211/25.12/files/package/kernel/mt76/patches/0049-mtk-mt76-mt7990-add-mt7987-wed-hw-path-support.patch'
    patch = raw('mediatek/mtk-openwrt-feeds', LOCK['mediatek_commit'], path, BUILD / 'mt76-wed-mt7987.patch')
    run(['git', 'apply', '--check', patch], BUILD / ('mt76-' + LOCK['mt76_commit']))


stage('upstream_turboacc_syntax_only', turboacc_syntax)
stage('prepare_6_12_94_source', prepare_kernel)
if RESULT['stages']['prepare_6_12_94_source'] == 'passed':
    stage('experimental_fullcone_and_nat_objects', compile_nat)
    stage('current_wed_baseline_objects', compile_wed_baseline)
    stage('vendor_wed_kernel_patch_dependencies', wed_kernel_dependency_check)
stage('vendor_mt76_patch_dependencies', wed_mt76_dependency_check)
print(json.dumps(RESULT, indent=2), flush=True)
raise SystemExit(1 if any(value != 'passed' for value in RESULT['stages'].values()) else 0)
