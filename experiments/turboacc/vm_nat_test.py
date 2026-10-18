"""Real fw4/UCI and packet tests, guarded to run only in the disposable VM.

All addresses are synthetic documentation prefixes; no router configuration
or personal identifiers are used. Hardware PPE/WED cannot be emulated here.
"""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

if 'turboacc_vm=1' not in Path('/proc/cmdline').read_text():
    raise SystemExit('Refusing network tests outside the disposable test VM')


def run(*args, check=True):
    return subprocess.run(args, text=True, capture_output=True, check=check)


def server():
    def udp(address):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((address, 3478))
            while True:
                _, peer = sock.recvfrom(1024)
                sock.sendto(json.dumps(peer).encode(), peer)
    def tcp():
        listener = socket.socket(); listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('198.51.100.2', 8080)); listener.listen()
        while True:
            connection, _ = listener.accept()
            def echo(sock):
                try:
                    while data := sock.recv(65536): sock.sendall(data)
                finally: sock.close()
            threading.Thread(target=echo, args=(connection,), daemon=True).start()
    for address in ['198.51.100.2', '198.51.100.3']:
        threading.Thread(target=udp, args=(address,), daemon=True).start()
    tcp()


def udp_client(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(2)
    sock.bind(('192.0.2.2', port)); mappings=[]
    for address in ['198.51.100.2', '198.51.100.3']:
        sock.sendto(b'probe', (address, 3478)); mappings.append(json.loads(sock.recv(1024)))
    print(json.dumps({'mappings': mappings}), flush=True)
    try: reached = sock.recv(1024) == b'unsolicited-third-peer'
    except socket.timeout: reached=False
    print(json.dumps({'third_peer_reached': reached}), flush=True)


def tcp_client():
    with socket.create_connection(('198.51.100.2', 8080), timeout=4) as sock:
        for _ in range(200):
            sock.sendall(b'actual-flow-offload-probe')
            if sock.recv(1024) != b'actual-flow-offload-probe': raise RuntimeError('TCP data mismatch')
            time.sleep(0.02)


def configuration(fullcone=0, hardware=0, cca='cubic'):
    Path('/etc/config/turboacc').write_text(f"config turboacc 'config'\n option fastpath 'flow_offloading'\n option fastpath_fo_hw '{hardware}'\n option fullcone '{fullcone}'\n option tcpcca '{cca}'\n")


def apply():
    result=run('/usr/libexec/turboacc-control', 'apply', check=False)
    if result.returncode:
        print(result.stdout, result.stderr, flush=True)
        error=Path('/tmp/turboacc-last-error')
        if error.exists():print(error.read_text(),flush=True)
        print('\n'.join(f'{index}: {line}' for index,line in enumerate(run('fw4','print',check=False).stdout.splitlines(),1)),flush=True)
        raise RuntimeError('Actual TurboACC backend apply failed')
    return json.loads(result.stdout)


def udp_probe(port):
    child=subprocess.Popen(['ip','netns','exec','client',sys.executable,__file__,'udp-client',str(port)],stdout=subprocess.PIPE,text=True)
    first=child.stdout.readline(); data=json.loads(first)
    endpoint=data['mappings'][0]
    sender="import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('198.51.100.4',3480));s.sendto(b'unsolicited-third-peer',(%r,%d))"%(endpoint[0],endpoint[1])
    run('ip','netns','exec','external',sys.executable,'-c',sender)
    rest,_=child.communicate(timeout=5)
    assert child.returncode==0
    data.update(json.loads(rest.strip()))
    return data


def main():
    results={}
    for name in ['client','external']:run('ip','netns','add',name)
    for root,peer,namespace in [('lan0','client0','client'),('wan0','external0','external')]:
        run('ip','link','add',root,'type','veth','peer','name',peer)
        run('ip','link','set',peer,'netns',namespace)
        run('ip','link','set',root,'up')
        run('ip','-n',namespace,'link','set','lo','up')
        run('ip','-n',namespace,'link','set',peer,'up')
    run('ip','-n','client','addr','add','192.0.2.2/24','dev','client0')
    run('ip','-n','client','route','add','default','via','192.0.2.1')
    for address in ['198.51.100.2/24','198.51.100.3/24','198.51.100.4/24']:
        run('ip','-n','external','addr','add',address,'dev','external0')
    Path('/etc/config/network').write_text("config interface 'lan'\n option device 'lan0'\n option proto 'static'\n option ipaddr '192.0.2.1'\n option netmask '255.255.255.0'\nconfig interface 'wan'\n option device 'wan0'\n option proto 'static'\n option ipaddr '198.51.100.1'\n option netmask '255.255.255.0'\n")
    Path('/etc/config/firewall').write_text("config defaults\n option input 'REJECT'\n option output 'ACCEPT'\n option forward 'REJECT'\nconfig zone\n option name 'lan'\n list network 'lan'\n option input 'ACCEPT'\n option output 'ACCEPT'\n option forward 'ACCEPT'\nconfig zone\n option name 'wan'\n list network 'wan'\n option input 'REJECT'\n option output 'ACCEPT'\n option forward 'REJECT'\n option masq '1'\nconfig forwarding\n option src 'lan'\n option dest 'wan'\n")
    subprocess.Popen(['/sbin/ubusd']);time.sleep(0.3)
    subprocess.Popen(['/sbin/netifd']);time.sleep(2)
    print(run('ubus','call','network.interface','dump').stdout,flush=True)
    server_process=subprocess.Popen(['ip','netns','exec','external',sys.executable,__file__,'server'])
    time.sleep(0.5)
    network_hash=hashlib.sha256(Path('/etc/config/network').read_bytes()).hexdigest()
    configuration(0,0,'reno'); before=apply()
    assert before['tcp_congestion_control']=='reno' and before['software_rules_active']
    assert before['fullcone_mode']==0
    results['apply_real_fw4_and_tcpcca']=True
    rpc='/usr/libexec/rpcd/luci.turboacc'
    methods=json.loads(run(rpc,'list').stdout)
    assert len(methods)==5
    features=json.loads(run(rpc,'call','getSystemFeatures').stdout)
    assert features['hasFLOWOFFLOADING'] is True and features['hasMEDIATEKHNAT'] is False
    assert 'Netfilter' in json.loads(run(rpc,'call','getFastPathStat').stdout)['type']
    assert json.loads(run(rpc,'call','getMTKPPEStat').stdout)=={'PPE_NUM':0}
    results['original_turboacc_rpc_contract_reports_real_backend_state']=True
    off=udp_probe(41000);assert not off['third_peer_reached'],off
    results['ordinary_nat_blocks_unknown_udp_peer']=True
    configuration(2,0,'cubic'); after=apply()
    assert after['fullcone_mode']==2 and after['tcp_congestion_control']=='cubic'
    assert 'Broadcom' in json.loads(run(rpc,'call','getFullConeStat').stdout)['type']
    assert json.loads(run(rpc,'call','getTCPCCAStat').stdout)['type']=='cubic'
    on=udp_probe(41002)
    assert on['mappings'][0]==on['mappings'][1],on
    assert on['third_peer_reached'],on
    results['fullcone_endpoint_independent_mapping_and_filtering']=True
    client=subprocess.Popen(['ip','netns','exec','client',sys.executable,__file__,'tcp-client'])
    time.sleep(1)
    entries=Path('/proc/net/nf_conntrack').read_text()
    assert 'OFFLOAD' in entries,entries
    client.wait(timeout=8);assert client.returncode==0
    results['tcp_data_and_actual_software_flow_offload']=True
    original=Path('/etc/config/firewall').read_bytes()
    configuration(3,0)
    assert run('/usr/libexec/turboacc-control','apply',check=False).returncode!=0
    assert Path('/etc/config/firewall').read_bytes()==original
    configuration(2,1)
    assert run('/usr/libexec/turboacc-control','apply',check=False).returncode!=0
    assert Path('/etc/config/firewall').read_bytes()==original
    results['invalid_mode_and_unavailable_ppe_rejected_without_firewall_changes']=True
    # Exercise the actual fw4 validation failure path, rather than a mock.
    configuration(0,0,'reno')
    config=Path('/etc/config/turboacc')
    config.write_text(config.read_text().replace("'flow_offloading'","'disabled'"))
    bad_include=Path('/etc/nftables.d/99-invalid-turboacc-test.nft')
    bad_include.write_text('deliberately_invalid_nft_statement\n')
    rejected=run('/usr/libexec/turboacc-control','apply',check=False)
    bad_include.unlink()
    assert rejected.returncode!=0
    assert Path('/etc/config/firewall').read_bytes()==original
    restored=json.loads(run('/usr/libexec/turboacc-control','status').stdout)
    assert restored['software_rules_active'] and restored['fullcone_mode']==2 and restored['tcp_congestion_control']=='cubic'
    results['real_fw4_failure_restores_firewall_and_keeps_previous_runtime']=True
    run('uci','set','firewall.@defaults[0].input=DROP')
    assert run('/usr/libexec/turboacc-control','apply',check=False).returncode!=0
    assert 'input=' in run('uci','changes','firewall').stdout
    assert Path('/etc/config/firewall').read_bytes()==original
    run('uci','revert','firewall')
    results['unrelated_pending_firewall_changes_preserved']=True
    configuration(0,0);apply();off_again=udp_probe(41004)
    assert not off_again['third_peer_reached'],off_again
    assert json.loads(run(rpc,'call','getFullConeStat').stdout)=={}
    results['disable_fullcone_restores_restricted_inbound_udp']=True
    assert hashlib.sha256(Path('/etc/config/network').read_bytes()).hexdigest()==network_hash
    results['network_and_interface_configuration_unchanged']=True
    status=json.loads(run('/usr/libexec/turboacc-control','status').stdout)
    assert status['wed_attached'] is False and status['ppe_bound_connections']==0
    results['absent_hardware_not_reported_as_running']=True
    print('TURBOACC_VM_RESULTS='+json.dumps(results),flush=True)
    print('TURBOACC_VM_TESTS_PASSED',flush=True)
    server_process.terminate()


if len(sys.argv)>1:
    if sys.argv[1]=='server':server()
    elif sys.argv[1]=='udp-client':udp_client(int(sys.argv[2]))
    elif sys.argv[1]=='tcp-client':tcp_client()
else:
    try:main()
    except Exception:
        print(run('nft','list','ruleset',check=False).stdout,flush=True)
        print(run('dmesg',check=False).stdout[-6000:],flush=True)
        raise
