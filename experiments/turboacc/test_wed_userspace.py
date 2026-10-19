"""Run WED diagnostics with real OpenWrt ash/UCI/jshn in a disposable chroot.

No host /proc or /sys is mounted. All simulated driver registers and saved
module options are ordinary files under the temporary fixture root.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
from runtime_vm import ROOTFS_URL, ROOTFS_SHA

HERE = Path(__file__).resolve().parent


def validate():
    with tempfile.TemporaryDirectory(prefix='wed-userland-', dir=os.environ.get('RUNNER_TEMP')) as temporary:
        folder = Path(temporary)
        archive = folder / 'rootfs.tar.gz'
        with urllib.request.urlopen(ROOTFS_URL, timeout=90) as response, archive.open('wb') as output:
            shutil.copyfileobj(response, output)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != ROOTFS_SHA:
            raise RuntimeError('OpenWrt userspace fixture hash differs')
        root = folder / 'root'; root.mkdir()
        subprocess.run(['sudo', 'tar', '-xzf', archive, '-C', root], check=True)
        subprocess.run(['sudo', 'chown', '-R', f'{os.getuid()}:{os.getgid()}', root], check=True)
        null = root / 'dev/null'
        subprocess.run(['sudo', 'mknod', '-m', '666', null, 'c', '1', '3'], check=True)
        def write(name, data):
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink(): path.unlink()
            path.write_text(data)
            return path
        helper = root / 'usr/libexec/turboacc-wed'
        helper.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / 'turboacc-wed', helper); helper.chmod(0o755)
        def run(operation, check=True):
            result = subprocess.run(['sudo', 'chroot', root, '/usr/libexec/turboacc-wed', operation],
                                    text=True, capture_output=True)
            if check and result.returncode:
                raise RuntimeError('WED userspace error: ' + result.stderr)
            return result
        def state(): return json.loads(run('status').stdout)
        write('etc/config/turboacc', "config turboacc 'config'\n option wed_enable '0'\n")
        absent = state()
        assert absent['health'] == 'unavailable' and absent['supported'] is False
        run('apply')  # Disabled and unsupported hardware must be a no-op.
        write('sys/module/mt7996e/parameters/wed_enable', 'Y\n')
        write('sys/kernel/debug/wed0/txinfo', '')
        dmesg = write('bin/dmesg', "#!/bin/sh\nprintf '%s\\n' 'mt7996e: failed to attach WED device -22'\n")
        dmesg.chmod(0o755)
        write('tmp/turboacc-last-error', 'Synthetic failure with "quotes" and <angle brackets>')
        failed = state()
        assert failed['health'] == 'failed' and failed['attached'] is False
        assert '"quotes"' in failed['apply_error'] and failed['reboot_pending'] is True
        write('sys/kernel/debug/wed0/txinfo', 'WED_TX_RING_BASE 00000001\n')
        attached = state()
        assert attached['health'] == 'attached' and attached['attached'] is True
        modules = write('etc/modules.conf', '# retained\noptions other test=3\noptions mt7996e extra=7 wed_enable=0 # preserved\noptions mt7996e wed_enable=0 other=9\n')
        write('etc/config/turboacc', "config turboacc 'config'\n option wed_enable '1'\n")
        run('apply'); once = modules.read_bytes()
        assert once.count(b'wed_enable=1') == 1 and b'wed_enable=0' not in once
        assert b'extra=7' in once and b'# preserved' in once and b'options other test=3' in once
        run('apply'); assert modules.read_bytes() == once
        write('etc/config/turboacc', "config turboacc 'config'\n option wed_enable '0'\n")
        run('apply'); assert modules.read_bytes().count(b'wed_enable=0') == 1
        previous = modules.read_bytes()
        write('etc/config/turboacc', "config turboacc 'config'\n option wed_enable '2'\n")
        assert run('apply', check=False).returncode != 0 and modules.read_bytes() == previous
        print('WED_OPENWRT_USERSPACE_PASSED: absent/failed/attached, escaped logs, boot-option roundtrip, idempotence, invalid-value protection')
        # RPC adapter compatibility with actual ash/UCI/jshn. Controller calls
        # are a synthetic marker here; real Netfilter packets are tested in VM.
        adapter=root/'usr/libexec/turboacc-ui'
        shutil.copyfile(HERE/'turboacc-ui',adapter);adapter.chmod(0o755)
        write('proc/sys/net/ipv4/tcp_available_congestion_control','reno cubic\n')
        write('proc/sys/net/netfilter/nf_conntrack_nat_tcp','0\n')
        controller=write('usr/libexec/turboacc-control','''#!/bin/sh
if [ "$1" = apply ]; then
 [ ! -f /tmp/ui-fail-apply ] || { echo 'Synthetic controller rejection' > /tmp/turboacc-last-error; exit 1; }
 touch /tmp/ui-applied
fi
echo '{"software_rules_active":false,"hardware_rules_active":false,"ppe_bound_connections":0}'
''');controller.chmod(0o755)
        write('etc/config/turboacc',"config turboacc 'config'\n option fastpath 'disabled'\n option fullcone '0'\n option fullcone_tcp '0'\n option tcpcca 'cubic'\n option wed_enable '0'\n")
        def request(payload):
            return subprocess.run(['sudo','chroot',root,'/usr/libexec/turboacc-ui','save'],input=json.dumps(payload),text=True,capture_output=True)
        payload=dict(software=False,hardware=False,wed=False,nat='0',nat_tcp=False,cca='reno',risk_confirmed=False)
        saved=request(payload)
        assert saved.returncode==0,(saved.stdout,saved.stderr)
        assert json.loads(saved.stdout)['configured']['cca']=='reno'
        assert (root/'tmp/ui-applied').exists()
        (root/'tmp/ui-applied').unlink()
        before=(root/'etc/config/turboacc').read_bytes()
        for invalid in [dict(payload,software='true'),dict(payload,nat='2'),dict(payload,nat='3')]:
            rejected=request(invalid)
            assert rejected.returncode and json.loads(rejected.stdout)['ok'] is False
            assert not (root/'tmp/ui-applied').exists()
            assert (root/'etc/config/turboacc').read_bytes()==before
        write('tmp/ui-fail-apply','fail\n')
        rejected=request(dict(payload,cca='cubic'))
        assert rejected.returncode and (root/'etc/config/turboacc').read_bytes()==before
        print('CARD_RPC_USERSPACE_PASSED: EOF input, strict types, security confirmation, real UCI save and controller-failure rollback')
        subprocess.run(['sudo','chown','-Rh',f'{os.getuid()}:{os.getgid()}',root],check=True)


if __name__ == '__main__':
    validate()
