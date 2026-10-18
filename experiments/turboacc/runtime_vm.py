"""Boot patched Netfilter and actual OpenWrt userspace in a disposable QEMU VM."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
ROOTFS_URL='https://downloads.openwrt.org/releases/25.12.5/targets/x86/64/openwrt-25.12.5-x86-64-rootfs.tar.gz'
ROOTFS_SHA='2dae4250b1b742062ed5787adcdc9dd6d26c7f69f94ced46548eb512d5957e8a'


def verify_runtime(build, download, run):
    vm=build/'runtime-vm';vm.mkdir()
    kernel=vm/'kernel';kernel.mkdir()
    run(['tar','-xf',build/'linux.tar.xz','-C',kernel,'--strip-components=1'],vm)
    run(['git','apply',HERE/'bcm-fullcone-6.12-experimental.patch'],kernel)
    run(['make','ARCH=x86_64','tinyconfig'],kernel)
    features='64BIT X86_64 BLK_DEV_INITRD RD_GZIP BINFMT_ELF BINFMT_SCRIPT PRINTK TTY SERIAL_8250 SERIAL_8250_CONSOLE UNIX98_PTYS SYSCTL PROC_FS PROC_SYSCTL SYSFS TMPFS SHMEM DEVTMPFS NET NET_NS NAMESPACES UTS_NS PID_NS IPC_NS USER_NS NETDEVICES NET_CORE VETH INET IPV6 IP_ADVANCED_ROUTER IP_MULTIPLE_TABLES PACKET UNIX NETFILTER NETFILTER_ADVANCED NF_CONNTRACK NF_CONNTRACK_PROCFS NF_CONNTRACK_EVENTS NF_NAT NF_NAT_MASQUERADE NF_DEFRAG_IPV4 NF_DEFRAG_IPV6 NF_TABLES NF_TABLES_INET NFT_CT NFT_LOG NFT_LIMIT NFT_REJECT NFT_REJECT_INET NF_REJECT_IPV4 NF_REJECT_IPV6 NFT_MASQ NFT_CHAIN_NAT NFT_FIB NFT_FIB_INET NFT_FIB_IPV4 NFT_FIB_IPV6 NFT_FLOW_OFFLOAD NF_FLOW_TABLE NF_FLOW_TABLE_INET TCP_CONG_CUBIC CHECKPOINT_RESTORE EPOLL SIGNALFD TIMERFD EVENTFD POSIX_TIMERS FUTEX FILE_LOCKING MULTIUSER INOTIFY_USER SYSVIPC'.split()
    features += ['NFT_NAT', 'NFT_REDIR', 'NFT_REJECT_IPV4', 'NFT_REJECT_IPV6', 'NFT_RT', 'DEBUG_FS']
    args=['scripts/config']
    for feature in features:args+=['--enable',feature]
    run(args,kernel)
    run(['make','ARCH=x86_64','olddefconfig'],kernel)
    config=(kernel/'.config').read_text()
    for feature in ['64BIT','NET_NS','VETH','NF_NAT','NFT_MASQ','NF_FLOW_TABLE','PROC_FS']:
        if 'CONFIG_'+feature+'=y' not in config:raise RuntimeError('VM configuration missing '+feature)
    run(['make','-j4','ARCH=x86_64','bzImage'],kernel)
    archive=download(ROOTFS_URL,vm/'rootfs.tar.gz')
    if hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()!=ROOTFS_SHA:raise RuntimeError('OpenWrt rootfs checksum mismatch')
    root=vm/'root';root.mkdir()
    run(['sudo','tar','-xzf',archive,'-C',root],vm)
    run(['sudo','chown','-R',f'{os.getuid()}:{os.getgid()}',root],vm)
    (root/'tmp').mkdir(exist_ok=True)
    # Minimal rootfs archives contain an empty /dev. TLS needs its entropy
    # devices even when package installation is performed in a chroot.
    for name,major,minor in [('null',1,3),('zero',1,5),('random',1,8),('urandom',1,9),('console',5,1)]:
        if not (root/'dev'/name).exists():run(['sudo','mknod','-m','666',root/'dev'/name,'c',str(major),str(minor)],vm)
    resolver=root/'etc/resolv.conf';resolver.unlink(missing_ok=True);shutil.copyfile('/etc/resolv.conf',resolver)
    run(['sudo','chroot',root,'/usr/bin/apk','add','--no-cache','--no-scripts','python3','ip-full','firewall4','nftables-json','uci','ubus','netifd','jsonfilter'],vm)
    # Package scripts are deliberately not executed in the host's network
    # namespace. Resolve only the executable alternatives inside this rootfs.
    if not (root/'usr/libexec/ip-full').is_file():raise RuntimeError('ip-full payload is missing')
    ip=root/'sbin/ip';ip.unlink(missing_ok=True);ip.symlink_to('/usr/libexec/ip-full')
    python_versions=sorted(path for path in (root/'usr/bin').glob('python3.*') if path.name.split('.')[-1].isdigit())
    if python_versions:
        python=root/'usr/bin/python3';python.unlink(missing_ok=True);python.symlink_to(python_versions[-1].name)
    resolver.write_text('nameserver 192.0.2.1\n')
    from prepare_package import prepare
    package=prepare(vm/'turboacc-package')
    for path in [package/'root/etc/init.d/turboacc',package/'root/usr/libexec/rpcd/luci.turboacc',package/'root/usr/libexec/turboacc-control']:
        run(['sh','-n',path],vm)
    run(['node','--check',package/'htdocs/luci-static/resources/view/turboacc.js'],vm)
    shutil.copytree(package/'root',root,dirs_exist_ok=True)
    tests=root/'root/acceleration';tests.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(HERE/'vm_nat_test.py',tests/'vm_nat_test.py')
    init=root/'init'
    init.write_text('''#!/bin/sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mkdir -p /var/run/ubus /var/lock /var/run/netns /sys/kernel/debug
mount -t debugfs debugfs /sys/kernel/debug || true
echo 1 > /proc/sys/net/ipv4/ip_forward
python3 /root/acceleration/vm_nat_test.py
rc=$?
echo TURBOACC_VM_TEST_EXIT=$rc
sync
reboot -f
''');init.chmod(0o755)
    if not (root/'dev/console').exists():run(['sudo','mknod',root/'dev/console','c','5','1'],vm)
    image=vm/'initramfs.cpio.gz'
    with image.open('wb') as output:
        process=subprocess.run(['sudo','sh','-c','find . -print0 | cpio --null -o --format=newc 2>/dev/null | gzip -1'],cwd=root,stdout=output,check=True)
    acceleration='kvm' if os.access('/dev/kvm',os.R_OK|os.W_OK) else 'tcg'
    command=['qemu-system-x86_64','-accel',acceleration,'-cpu','host' if acceleration=='kvm' else 'max','-m','768M','-nographic','-no-reboot','-nic','none','-kernel',str(kernel/'arch/x86/boot/bzImage'),'-initrd',str(image),'-append','console=ttyS0 init=/init panic=1 turboacc_vm=1']
    result=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
    print(result.stdout,flush=True)
    if 'TURBOACC_VM_TESTS_PASSED' not in result.stdout or 'TURBOACC_VM_TEST_EXIT=0' not in result.stdout:
        raise RuntimeError('Real fw4/Netfilter packet tests did not pass')
