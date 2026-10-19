"""Real fw4/UCI and packet tests, guarded to run only in the disposable VM.

All addresses are synthetic documentation prefixes; no router configuration
or personal identifiers are used. Hardware PPE/WED cannot be emulated here.
"""
import hashlib
import json
from pathlib import Path
import socket
import signal
import subprocess
import sys
import threading
import time

if 'turboacc_vm=1' not in Path('/proc/cmdline').read_text():
    raise SystemExit('Refusing network tests outside the disposable test VM')


def run(*args, check=True):
    result = subprocess.run(args, text=True, capture_output=True)
    if check and result.returncode:
        print(result.stdout, result.stderr, flush=True)
        result.check_returncode()
    return result


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
                    while data := sock.recv(65536): sock.sendall(json.dumps(sock.getpeername()).encode() if data == b'?mapping?' else data)
                finally: sock.close()
            threading.Thread(target=echo, args=(connection,), daemon=True).start()
    for address in ['198.51.100.2', '198.51.100.3']:
        threading.Thread(target=udp, args=(address,), daemon=True).start()
    tcp()


def udp_client(port, source):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(2)
    sock.bind((source, port))
    def refresh():
        mappings=[]
        for address in ['198.51.100.2', '198.51.100.3']:
            sock.sendto(b'probe', (address, 3478)); mappings.append(json.loads(sock.recv(1024)))
        print(json.dumps({'mappings': mappings}),flush=True)
    refresh()
    for line in sys.stdin:
        command=json.loads(line)
        if command['action']=='refresh':refresh()
        elif command['action']=='receive':
            try: reached=sock.recv(1024).decode()==command['token']
            except socket.timeout:reached=False
            print(json.dumps({'third_peer_reached':reached}),flush=True)


def tcp_client():
    stop=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    with socket.create_connection(('198.51.100.2', 8080), timeout=4) as sock:
        print('TCP_CLIENT_READY',flush=True)
        until=time.monotonic()+90
        while not stop.is_set() and time.monotonic()<until:
            expected=b'actual-flow-offload-probe';sock.sendall(expected);received=b''
            while len(received)<len(expected):
                chunk=sock.recv(len(expected)-len(received))
                if not chunk:raise RuntimeError('TCP stream closed early')
                received+=chunk
            if received != expected: raise RuntimeError('TCP data mismatch')
            time.sleep(0.02)


def tcp_cone_client(port, source):
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    listener.bind((source, port)); listener.listen(); listener.settimeout(2)
    outgoing = socket.socket()
    outgoing.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    outgoing.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    outgoing.bind((source, port)); outgoing.settimeout(2)
    outgoing.connect(('198.51.100.2', 8080))
    outgoing.sendall(b'?mapping?')
    print(json.dumps({'mapping': json.loads(outgoing.recv(1024))}), flush=True)
    for line in sys.stdin:
        command = json.loads(line)
        if command['action'] == 'receive':
            try:
                connection, peer = listener.accept()
                with connection:
                    connection.settimeout(2)
                    message = connection.recv(1024)
                    connection.sendall(message)
                    reached = message == command['token'].encode()
            except socket.timeout: reached = False
            print(json.dumps({'reached': reached}), flush=True)
    outgoing.close(); listener.close()


class TCPProbe:
    def __init__(self, port, source='192.0.2.2'):
        self.child = subprocess.Popen(['ip','netns','exec','client',sys.executable,__file__,'tcp-cone-client',str(port),source], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.mapping = json.loads(self.child.stdout.readline())['mapping']
        self.sequence = 0
    def receive_from(self, address='198.51.100.4'):
        self.sequence += 1; token = 'tcp-cone-' + str(self.sequence)
        self.child.stdin.write(json.dumps({'action':'receive','token':token})+'\n'); self.child.stdin.flush()
        sender = '''import socket,json
s=socket.socket();s.settimeout(1.5);s.bind((%r,0))
try:
 s.connect((%r,%d));s.sendall(%r);reached=s.recv(1024)==%r
except (OSError,socket.timeout): reached=False
print(json.dumps({'reached':reached}))
''' % (address,self.mapping[0],self.mapping[1],token.encode(),token.encode())
        external = json.loads(run('ip','netns','exec','external',sys.executable,'-c',sender).stdout)['reached']
        internal = json.loads(self.child.stdout.readline())['reached']
        assert external == internal
        print('TURBOACC_TCP_PACKET_RESULT='+json.dumps({'mapping':self.mapping,'sender':address,'reached':internal}),flush=True)
        return internal
    def __enter__(self): return self
    def __exit__(self,*_):
        self.child.stdin.close(); self.child.wait(timeout=5); assert self.child.returncode == 0


def configuration(fullcone=0, hardware=0, cca='cubic', protocol='udp', tcp=False):
    Path('/etc/config/turboacc').write_text(f"config turboacc 'config'\n option fastpath 'flow_offloading'\n option fastpath_fo_hw '{hardware}'\n option fullcone '{fullcone}'\n option fullcone_protocol '{protocol}'\n option fullcone_tcp '{int(tcp)}'\n option tcpcca '{cca}'\n")


def apply():
    result=run('/usr/libexec/turboacc-control', 'apply', check=False)
    if result.returncode:
        print(result.stdout, result.stderr, flush=True)
        error=Path('/tmp/turboacc-last-error')
        if error.exists():print(error.read_text(),flush=True)
        print('\n'.join(f'{index}: {line}' for index,line in enumerate(run('fw4','print',check=False).stdout.splitlines(),1)),flush=True)
        raise RuntimeError('Actual TurboACC backend apply failed')
    return json.loads(result.stdout)


class UDPProbe:
    def __init__(self,port,source='192.0.2.2'):
        self.child=subprocess.Popen(['ip','netns','exec','client',sys.executable,__file__,'udp-client',str(port),source],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        self.mappings=json.loads(self.child.stdout.readline())['mappings'];self.sequence=0
    def command(self,value):
        self.child.stdin.write(json.dumps(value)+'\n');self.child.stdin.flush()
        return json.loads(self.child.stdout.readline())
    def refresh(self):
        self.mappings=self.command({'action':'refresh'})['mappings']
        assert self.mappings[0]==self.mappings[1],self.mappings
    def receive_from(self,address='198.51.100.4',port=3480):
        self.sequence+=1;token='udp-packet-'+str(self.sequence)
        endpoint=self.mappings[0]
        sender="import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind((%r,%d));s.sendto(%r,(%r,%d))"%(address,port,token.encode(),endpoint[0],endpoint[1])
        run('ip','netns','exec','external',sys.executable,'-c',sender)
        reached=self.command({'action':'receive','token':token})['third_peer_reached']
        print('TURBOACC_UDP_PACKET_RESULT='+json.dumps({'mappings':self.mappings,'sender':address,'sender_port':port,'reached':reached}),flush=True)
        return reached
    def __enter__(self):return self
    def __exit__(self,*_):
        self.child.stdin.close();self.child.wait(timeout=5)
        assert self.child.returncode==0


def main():
    class Results(dict):
        def __setitem__(self,name,value):
            super().__setitem__(name,value)
            print('TURBOACC_VM_CHECK='+name+': '+str(value),flush=True)
    results=Results()
    for name in ['client','external']:run('ip','netns','add',name)
    for root,peer,namespace in [('lan0','client0','client'),('wan0','external0','external')]:
        run('ip','link','add',root,'type','veth','peer','name',peer)
        run('ip','link','set',peer,'netns',namespace)
        run('ip','link','set',root,'up')
        run('ip','-n',namespace,'link','set','lo','up')
        run('ip','-n',namespace,'link','set',peer,'up')
    run('ip','-n','client','addr','add','192.0.2.2/24','dev','client0')
    run('ip','-n','client','addr','add','192.0.2.3/24','dev','client0')
    run('ip','-n','client','route','add','default','via','192.0.2.1')
    for address in ['198.51.100.2/24','198.51.100.3/24','198.51.100.4/24']:
        run('ip','-n','external','addr','add',address,'dev','external0')
    Path('/etc/config/network').write_text("config interface 'lan'\n option device 'lan0'\n option proto 'static'\n option ipaddr '192.0.2.1'\n option netmask '255.255.255.0'\nconfig interface 'wan'\n option device 'wan0'\n option proto 'static'\n option ipaddr '198.51.100.1'\n option netmask '255.255.255.0'\n")
    Path('/etc/config/firewall').write_text("config defaults\n option input 'REJECT'\n option output 'ACCEPT'\n option forward 'REJECT'\nconfig zone\n option name 'lan'\n list network 'lan'\n option input 'ACCEPT'\n option output 'ACCEPT'\n option forward 'ACCEPT'\nconfig zone\n option name 'wan'\n list network 'wan'\n option input 'REJECT'\n option output 'ACCEPT'\n option forward 'REJECT'\n option masq '1'\nconfig forwarding\n option src 'lan'\n option dest 'wan'\n")
    subprocess.Popen(['/sbin/ubusd']);time.sleep(0.3)
    subprocess.Popen(['/sbin/netifd']);time.sleep(2)
    print(run('ubus','call','network.interface','dump').stdout,flush=True)
    initial_firewall=run('fw4','start',check=False)
    if initial_firewall.returncode:
        print(initial_firewall.stdout,initial_firewall.stderr,flush=True)
        print(run('fw4','print',check=False).stdout,flush=True)
        raise RuntimeError('The actual OpenWrt baseline firewall could not start')
    server_process=subprocess.Popen(['ip','netns','exec','external',sys.executable,__file__,'server'])
    time.sleep(0.5)
    network_hash=hashlib.sha256(Path('/etc/config/network').read_bytes()).hexdigest()
    assert Path('/proc/sys/net/netfilter/nf_conntrack_nat_mode').read_text().strip()=='0'
    assert run('uci','-q','get','turboacc.config.fullcone').stdout.strip()=='0'
    assert run('uci','-q','get','turboacc.config.fullcone_protocol').stdout.strip()=='udp'
    results['fullcone_kernel_and_package_default_disabled']=True
    configuration(0,0,'reno'); before=apply()
    assert before['tcp_congestion_control']=='reno' and before['software_rules_active']
    assert before['fullcone_mode']==0
    results['apply_real_fw4_and_tcpcca']=True
    rpc='/usr/libexec/rpcd/luci.turboacc'
    methods=json.loads(run(rpc,'list').stdout)
    assert {'getSystemFeatures','getFastPathStat','getFullConeStat','getTCPCCAStat','getMTKPPEStat','getWedStat','getUiStatus','saveUiSettings'} == set(methods)
    wed=json.loads(run(rpc,'call','getWedStat').stdout)
    assert wed['supported'] is False and wed['attached'] is False and wed['health']=='unavailable'
    results['wed_diagnostics_does_not_claim_nonexistent_hardware']=True
    features=json.loads(run(rpc,'call','getSystemFeatures').stdout)
    assert features['hasFLOWOFFLOADING'] is True and features['hasMEDIATEKHNAT'] is False
    assert 'Netfilter' in json.loads(run(rpc,'call','getFastPathStat').stdout)['type']
    assert json.loads(run(rpc,'call','getMTKPPEStat').stdout)=={'PPE_NUM':0}
    results['original_turboacc_rpc_contract_reports_real_backend_state']=True
    with UDPProbe(41000) as probe:assert not probe.receive_from()
    results['ordinary_nat_blocks_unknown_udp_peer']=True

    configuration(1,0,'cubic');restricted=apply()
    assert restricted['fullcone_mode']==1
    assert 'Address-restricted' in json.loads(run(rpc,'call','getFullConeStat').stdout)['type']
    with UDPProbe(41002) as probe:
        assert probe.mappings[0]==probe.mappings[1]
        assert not probe.receive_from()
        assert probe.receive_from('198.51.100.2',3480)
        with UDPProbe(41002,'192.0.2.3') as second:
            assert second.mappings[0]==second.mappings[1]
            assert second.mappings[0]!=probe.mappings[0]
            assert second.receive_from('198.51.100.2',3480)
    results['restricted_cone_allows_contacted_ip_new_port_and_blocks_unknown_ip']=True
    results['restricted_cone_prevents_two_clients_claiming_same_external_port']=True

    client=subprocess.Popen(['ip','netns','exec','client',sys.executable,__file__,'tcp-client'],stdout=subprocess.PIPE,text=True)
    assert client.stdout.readline().strip()=='TCP_CLIENT_READY'
    time.sleep(1)
    entries=Path('/proc/net/nf_conntrack').read_text()
    tcp_entries=[line for line in entries.splitlines()
                 if ' tcp ' in ' '+line and 'dst=198.51.100.2 ' in line and 'dport=8080 ' in line]
    assert any('[OFFLOAD]' in line for line in tcp_entries),entries
    print('TURBOACC_TCP_CONNTRACK='+json.dumps(tcp_entries),flush=True)
    results['tcp_data_and_actual_software_flow_offload']=True

    configuration(2,0,'cubic'); after=apply()
    assert after['fullcone_mode']==2 and after['tcp_congestion_control']=='cubic'
    assert 'Broadcom' in json.loads(run(rpc,'call','getFullConeStat').stdout)['type']
    assert json.loads(run(rpc,'call','getTCPCCAStat').stdout)['type']=='cubic'
    with UDPProbe(41004) as probe:
        assert probe.mappings[0]==probe.mappings[1]
        assert probe.receive_from()
        assert probe.receive_from('198.51.100.2',3480)
        results['fullcone_endpoint_independent_mapping_and_filtering']=True
        configuration(1,0);apply()
        # Keep the same bound socket open. Neither old wildcard expectations
        # nor previously accepted RELATED child connections may survive.
        assert not probe.receive_from()
        assert not probe.receive_from('198.51.100.2',3480)
        probe.refresh()
        assert not probe.receive_from()
        assert probe.receive_from('198.51.100.2',3480)
        results['full_to_restricted_removes_old_wildcard_and_related_flows']=True
        configuration(0,0);apply()
        assert not probe.receive_from()
        assert not probe.receive_from('198.51.100.2',3480)
        probe.refresh()
        assert not probe.receive_from()
        assert not probe.receive_from('198.51.100.2',3480)
        results['disabled_mode_removes_existing_cone_state_and_restores_default_nat']=True
    assert client.poll() is None
    configuration(2,0);apply()
    original=Path('/etc/config/firewall').read_bytes()
    configuration(3,0)
    assert run('/usr/libexec/turboacc-control','apply',check=False).returncode!=0
    assert Path('/etc/config/firewall').read_bytes()==original
    configuration(2,0,protocol='tcp')
    assert run('/usr/libexec/turboacc-control','apply',check=False).returncode!=0
    assert Path('/etc/config/firewall').read_bytes()==original
    assert json.loads(run('/usr/libexec/turboacc-control','status').stdout)['fullcone_mode']==2
    results['non_udp_cone_configuration_rejected_without_runtime_changes']=True
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
    assert Path('/proc/sys/net/netfilter/nf_conntrack_nat_tcp').read_text().strip() == '0'
    # Full cone remains UDP-only until TCP is explicitly opted in.
    configuration(2,0,tcp=False);apply()
    with TCPProbe(42000) as tcp_probe: assert not tcp_probe.receive_from()
    results['udp_fullcone_does_not_enable_tcp_cone']=True
    configuration(1,0,tcp=True);apply()
    with TCPProbe(42002) as tcp_probe:
        assert not tcp_probe.receive_from()
        assert tcp_probe.receive_from('198.51.100.2')
        with TCPProbe(42002,'192.0.2.3') as other:
            assert other.mapping != tcp_probe.mapping
            assert other.receive_from('198.51.100.2')
    results['restricted_tcp_handshake_data_and_collision_isolation']=True
    configuration(2,0,tcp=True);apply()
    with TCPProbe(42004) as tcp_probe:
        assert tcp_probe.receive_from()
        configuration(1,0,tcp=True);apply()
        assert not tcp_probe.receive_from()
        assert not tcp_probe.receive_from('198.51.100.2')
    results['tcp_full_to_restricted_clears_old_wildcard_expectations']=True
    configuration(2,0,tcp=True);apply()
    with TCPProbe(42006) as tcp_probe:
        assert tcp_probe.receive_from()
        configuration(2,0,tcp=False);apply()
        assert not tcp_probe.receive_from()
        assert not tcp_probe.receive_from('198.51.100.2')
    assert client.poll() is None
    results['tcp_opt_out_restores_default_without_killing_ordinary_tcp']=True
    configuration(0,0);apply()
    with UDPProbe(41006) as probe:assert not probe.receive_from()
    assert 'System default' in json.loads(run(rpc,'call','getFullConeStat').stdout)['type']
    assert client.poll() is None
    client.terminate();client.wait(timeout=5);assert client.returncode==0
    results['same_tcp_connection_survives_udp_nat_mode_changes']=True
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
    elif sys.argv[1]=='udp-client':udp_client(int(sys.argv[2]),sys.argv[3])
    elif sys.argv[1]=='tcp-client':tcp_client()
    elif sys.argv[1]=='tcp-cone-client':tcp_cone_client(int(sys.argv[2]),sys.argv[3])
else:
    try:main()
    except Exception:
        print(run('nft','list','ruleset',check=False).stdout,flush=True)
        print(run('dmesg',check=False).stdout[-6000:],flush=True)
        raise
