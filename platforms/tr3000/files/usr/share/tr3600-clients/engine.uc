import { readfile, writefile, rename, popen, lsdir, stat } from 'fs';
import { cursor } from 'uci';
import { connect } from 'ubus';

const STATE = '/tmp/tr3600-clients-state.json';
const RULES = '/tmp/tr3600-clients-rules.nft';
const ERROR = '/tmp/tr3600-clients-error';
const TABLE = 'inet tr3600_clients';
let uci = cursor(), bus = connect();
function sh(s) { return "'" + replace(s, /'/g, "'\\''") + "'"; }
function run(cmd) {
    let p = popen(cmd, 'r');
    if (!p) return { code: 1, text: '' };
    let text = p.read('all');
    return { code: p.close(), text: text || '' };
}
function parse(s, fallback) { try { return json(s); } catch (e) { return fallback; } }
function call(obj, method, args) { try { return bus.call(obj, method, args || {}) || {}; } catch (e) { return {}; } }
function macok(s) { return type(s) == 'string' && match(s, /^[0-9a-f][02468ace](:[0-9a-f]{2}){5}$/) && s != '00:00:00:00:00:00'; }
function ipok(s) { return type(s) == 'string' && (match(s, /^[0-9]{1,3}(\.[0-9]{1,3}){3}$/) || (index(s, ':') >= 0 && match(s, /^[0-9a-fA-F:]+$/))); }
function id(mac) { return replace(mac, /:/g, ''); }
function policy() {
    let result = {};
    uci.foreach('tr3600_clients', 'client', function(s) {
        if (macok(s.mac)) result[s.mac] = { alias: s.alias || '', blocked: s.blocked == '1', upload: +s.upload || 0, download: +s.download || 0 };
    });
    return result;
}
function inventory(dev, policies, previous) {
    let devices = {}, owners = {};
    function get(mac) {
        mac = lc(mac || '');
        if (!macok(mac)) return null;
        if (!devices[mac]) devices[mac] = { mac, name: '', addresses: [], online: false, connection: '未确认', signal: null };
        return devices[mac];
    }
    function addr(d, ip) {
        if (d && ipok(ip)) {
            owners[ip] = d.mac;
            if (index(d.addresses, ip) < 0) push(d.addresses, ip);
        }
    }
    for (let line in split(readfile('/tmp/dhcp.leases') || '', '\n')) {
        let f = split(trim(line), /\s+/);
        if (length(f) < 4 || (+f[0] != 0 && +f[0] < time())) continue;
        let d = get(f[1]); if (!d) continue;
        if (f[3] != '*') d.name = f[3];
        addr(d, f[2]);
    }
    for (let n in parse(run('ip -j neigh show dev ' + sh(dev)).text, [])) {
        if (index(n.state || [], 'FAILED') >= 0 || index(n.state || [], 'INCOMPLETE') >= 0) continue;
        let d = get(n.lladdr); if (!d) continue;
        addr(d, n.dst);
        if (index(n.state || [], 'REACHABLE') >= 0 || index(n.state || [], 'DELAY') >= 0 || index(n.state || [], 'PROBE') >= 0) d.online = true;
    }
    // Resolve Ethernet attachment from learned bridge ports, never from absence of Wi-Fi.
    let wired = {};
    for (let port in lsdir('/sys/class/net/' + dev + '/brif') || []) {
        if (index(call('iwinfo', 'devices').devices || [], port) >= 0) continue;
        let base = '/sys/class/net/' + port;
        if (!stat(base + '/device') || stat(base + '/phy80211') || index(readfile(base + '/uevent') || '', 'DEVTYPE=wlan') >= 0) continue;
        let number = trim(readfile(base + '/brport/port_no') || '');
        if (number) wired[lc(number)] = true;
    }
    for (let line in split(run('brctl showmacs ' + sh(dev) + ' 2>/dev/null').text, '\n')) {
        let f = split(trim(line), /\s+/);
        if (length(f) < 4 || f[2] != 'no' || !wired[sprintf('0x%x', +f[0])]) continue;
        let mac = lc(f[1]);
        if (devices[mac]) devices[mac].connection = '有线';
    }
    // MediaTek vendor firmware exposes stations through iwinfo, not hostapd.*.
    for (let iface in call('iwinfo', 'devices').devices || []) {
        let info = call('iwinfo', 'info', { device: iface });
        if (info.mode != 'Master') continue;
        for (let rate in call('iwinfo', 'assoclist', { device: iface }).results || []) {
            let d = get(rate.mac); if (!d) continue;
            d.online = true;
            d.connection = info.frequency >= 5925 ? '6 GHz' : info.frequency >= 5000 ? '5 GHz' : '2.4 GHz';
            d.signal = rate.signal;
            let rx = rate.rx || {}, tx = rate.tx || {};
            d.protocol = rx.eht || tx.eht ? 'BE' : rx.he || tx.he ? 'AX' : rx.vht || tx.vht ? 'AC' : rx.ht || tx.ht ? 'N' : '';
        }
    }
    for (let mac, p in policies) get(mac);
    // Retain this boot's history after leases/neighbours expire, without stale IP rules.
    for (let old in previous) {
        let d = get(old.mac);
        if (d && !d.name) d.name = old.name || '';
    }
    let result = [];
    for (let mac, d in devices) {
        d.addresses = sort(filter(d.addresses, ip => owners[ip] == mac));
        d.policy = policies[mac] || { alias: '', blocked: false, upload: 0, download: 0 };
        push(result, d);
    }
    if (length(result) > 128) die('客户端超过 128 台，暂不应用规则');
    return sort(result, (a, b) => a.mac < b.mac ? -1 : (a.mac > b.mac ? 1 : 0));
}
function counters() {
    let r = run('nft -j list table ' + TABLE + ' 2>/dev/null'), counts = {};
    for (let e in parse(r.text, {}).nftables || []) if (e.counter) counts[e.counter.name] = e.counter.bytes;
    return { exists: r.code == 0, counts };
}
function offloading() {
    let ruleset = run('nft list ruleset').text;
    let active = !!match(ruleset, /flow\s+(add|offload)\s+@/);
    let hnat = trim(readfile('/sys/kernel/debug/hnat/hook_toggle') || '') == 'enabled';
    return { active: active || hnat, hardware: hnat || (active && !!match(ruleset, /flags\s+offload(\s|;|$)/)) };
}
function rules(dev, clients, exists) {
    let out = exists ? 'delete table ' + TABLE + '\n' : '';
    out += 'table ' + TABLE + ' {\n';
    let up = [], down = [];
    for (let d in clients) {
        let key = id(d.mac), p = d.policy;
        out += 'counter u' + key + ' {}\ncounter d' + key + ' {}\n';
        out += 'chain u' + key + ' {\n';
        // Keep DHCP, DNS and access to the router available, including when blocked.
        out += 'fib daddr type { local, broadcast, multicast } return\n';
        if (p.blocked) out += 'drop\n';
        else {
            if (p.upload) out += 'limit rate over ' + int(p.upload * 125000) + ' bytes/second burst 128000 bytes drop\n';
            out += 'counter name u' + key + '\n';
        }
        out += '}\nchain d' + key + ' {\n';
        // Local router replies remain accessible; rate limits concern routed/proxied data.
        if (p.blocked) out += 'fib saddr type != local drop\n';
        else {
            if (p.download) out += 'limit rate over ' + int(p.download * 125000) + ' bytes/second burst 128000 bytes drop\n';
            out += 'counter name d' + key + '\n';
        }
        out += '}\n';
        push(up, 'iifname ' + sprintf('%J', dev) + ' ether saddr ' + d.mac + ' jump u' + key);
        let v4 = [], v6 = [];
        for (let ip in d.addresses) push(index(ip, ':') >= 0 ? v6 : v4, ip);
        if (length(v4)) push(down, 'oifname ' + sprintf('%J', dev) + ' ip daddr { ' + join(', ', v4) + ' } jump d' + key);
        if (length(v6)) push(down, 'oifname ' + sprintf('%J', dev) + ' ip6 daddr { ' + join(', ', v6) + ' } jump d' + key);
    }
    // Run before OpenClash's usual prerouting redirection; never accept past fw4 policy.
    out += 'chain upload { type filter hook prerouting priority -190; policy accept;\n' + join('\n', up) + '\n}\n';
    out += 'chain download { type filter hook postrouting priority -1; policy accept;\n' + join('\n', down) + '\n}\n}\n';
    return out;
}
function tick(dry) {
    let settings = uci.get_all('tr3600_clients', 'main') || {};
    let iface = settings.interface || 'lan';
    if (!match(iface, /^[a-zA-Z0-9_]+$/)) die('无效接口名称');
    let lan = call('network.interface.' + iface, 'status'), dev = lan.l3_device;
    if (!dev || !match(dev, /^[a-zA-Z0-9_.-]{1,15}$/)) die('LAN 接口未就绪');
    let acceleration = offloading();
    let old = parse(readfile(STATE), {}), now = time();
    let clients = inventory(dev, policy(), old.clients || []);
    let signature = sprintf('%J', map(clients, d => ({mac: d.mac, addresses: d.addresses, policy: d.policy})));
    let c = counters(), rebuild = old.signature != signature || old.device != dev || !c.exists;
    let prev = {}; for (let d in old.clients || []) prev[d.mac] = d;
    for (let d in clients) {
        let p = prev[d.mac] || {};
        for (let direction in ['up', 'down']) {
            let raw = c.counts[(direction == 'up' ? 'u' : 'd') + id(d.mac)] || 0;
            let delta = raw >= (p[direction + '_raw'] || 0) ? raw - (p[direction + '_raw'] || 0) : raw;
            d[direction + '_bytes'] = (p[direction + '_bytes'] || 0) + delta;
            d[direction + '_rate'] = old.time && now > old.time ? delta / (now - old.time) : 0;
            d[direction + '_raw'] = rebuild ? 0 : raw;
        }
        if (d.up_rate > 0 || d.down_rate > 0) d.online = true;
    }
    if (rebuild || dry) {
        writefile(RULES, rules(dev, clients, c.exists));
        if (run('nft -c -f ' + sh(RULES) + ' 2>' + ERROR).code != 0) die('规则检查失败：' + (readfile(ERROR) || 'nft error'));
        if (!dry && run('nft -f ' + sh(RULES) + ' 2>' + ERROR).code != 0) die('规则应用失败：' + (readfile(ERROR) || 'nft error'));
    }
    if (!dry) {
        writefile(STATE + '.new', sprintf('%J', { ok: true, time: now, since: old.since || now, device: dev, signature, clients, offloading: acceleration }));
        rename(STATE + '.new', STATE);
        writefile(ERROR, '');
    }
    return { ok: true, clients: length(clients), dry: !!dry, offloading: acceleration };
}
function save(req) {
    let mac = lc(req.mac || '');
    if (!macok(mac)) die('无效 MAC 地址');
    if (type(req.alias) != 'string' || length(req.alias) > 64 || match(req.alias, /[[:cntrl:]]/)) die('别名最多 64 字节，不能含控制字符');
    for (let n in ['upload', 'download']) if (type(req[n]) != 'int' && type(req[n]) != 'double' || req[n] < 0 || req[n] > 2500 || (req[n] > 0 && req[n] < 1)) die('限速范围为 1–2500 Mbps，0 表示不限速');
    if (type(req.blocked) != 'bool') die('黑名单参数无效');
    if (offloading().active && (req.blocked || req.upload || req.download))
        die('请先关闭流量分载，再设置限速或黑名单');
    let section = 'c' + id(mac), original = readfile('/etc/config/tr3600_clients');
    try {
        uci.set('tr3600_clients', section, 'client');
        for (let name, value in { mac, alias: trim(req.alias), blocked: req.blocked ? '1' : '0', upload: '' + req.upload, download: '' + req.download }) uci.set('tr3600_clients', section, name, value);
        uci.save('tr3600_clients');
        tick(true);
        uci.commit('tr3600_clients');
        return tick(false);
    } catch (e) {
        uci.revert('tr3600_clients');
        writefile('/etc/config/tr3600_clients', original);
        die(e.message || "保存失败");
    }
}
try {
    let mode = ARGV[0], result;
    if (mode == 'status') {
        result = parse(readfile(STATE), { ok: false, clients: [], message: '正在读取设备…' });
        result.error = trim(readfile(ERROR) || '');
        result.stale = time() - (result.time || 0) > 20;
        result.offloading = offloading();
        delete result.signature;
    } else if (mode == 'save') result = save(parse(readfile('/dev/stdin'), {}));
    else if (mode == 'tick' || mode == 'check') result = tick(mode == 'check');
    else die('未知操作');
    if (mode != 'tick') print(sprintf('%J\n', result));
} catch (e) {
    let message = e.message || '' + e;
    if (ARGV[0] == 'tick') writefile(ERROR, message);
    print(sprintf('%J\n', { ok: false, message }));
    exit(1);
}
