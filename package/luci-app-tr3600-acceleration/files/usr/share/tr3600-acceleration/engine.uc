import { readfile, writefile, rename, unlink, popen, stat } from 'fs';
import { cursor } from 'uci';

const MODULES = '/etc/modules.conf';
let uci = cursor();
function run(cmd) {
    let p = popen(cmd, 'r');
    if (!p) return { code: 1, text: '' };
    let text = p.read('all');
    return { code: p.close(), text: text || '' };
}
function wedOption(text) {
    let value = null;
    for (let line in split(text || '', '\n')) {
        line = split(line, '#')[0];
        if (!match(line, /^\s*options\s+mt7996e\s/)) continue;
        for (let token in split(trim(line), /\s+/)) {
            let m = match(token, /^wed_enable=(.*)$/);
            if (m) value = index(['1', 'Y', 'y', 'true'], m[1]) >= 0;
        }
    }
    return value;
}
function setWedOption(text, value) {
    let lines = [], added = false;
    for (let line in split(text || '', '\n')) {
        let parts = split(line, '#'), code = parts[0];
        if (match(code, /^\s*options\s+mt7996e(\s|$)/)) {
            code = trim(replace(code, /\s+wed_enable=\S+/g, ''));
            if (!added) { code += ' wed_enable=' + (value ? '1' : '0'); added = true; }
            line = code + (length(parts) > 1 ? ' #' + join('#', slice(parts, 1)) : '');
        }
        push(lines, line);
    }
    if (!added) push(lines, 'options mt7996e wed_enable=' + (value ? '1' : '0'));
    return replace(join('\n', lines), /\n+$/, '') + '\n';
}
function policies() {
    let count = 0;
    uci.foreach('tr3600_clients', 'client', s => {
        if (s.blocked == '1' || +s.upload > 0 || +s.download > 0) count++;
    });
    return count;
}
function wedHealth(enabled, attached, readable, logs) {
    if (attached) return 'running';
    if (!enabled) return 'disabled';
    if (match(logs || '', /failed to attach wed device/)) return 'failed';
    return readable ? 'not_attached' : 'unknown';
}
function wedDiagnostics(enabled) {
    let attached = false, readable = false;
    // txinfo only emits registers while a WLAN device is attached; directory existence is insufficient.
    for (let name in ['wed0', 'wed1', 'wed2']) {
        let info = readfile('/sys/kernel/debug/' + name + '/txinfo');
        if (info == null) continue;
        readable = true;
        if (length(trim(info))) attached = true;
    }
    let result = run('dmesg 2>/dev/null'), lines = [];
    for (let line in split(result.text, '\n')) {
        if (match(line, /[Ww][Ee][Dd]/)) push(lines, line);
    }
    let logs = join('\n', slice(lines, -30));
    return { state: wedHealth(enabled, attached, readable, logs), logs,
        logs_available: result.code == 0 };
}
function status() {
    let section;
    uci.foreach('firewall', 'defaults', s => { if (!section) section = s; });
    if (!section) die('未找到防火墙全局配置');
    let forward = run('nft list chain inet fw4 forward 2>/dev/null');
    let table = run('nft list flowtable inet fw4 ft 2>/dev/null');
    let active = forward.code == 0 && table.code == 0 && !!match(forward.text, /flow (add|offload) @ft/);
    let hardware = active && !!match(table.text, /flags\s+offload(\s|;|$)/);
    let parameter = trim(readfile('/sys/module/mt7996e/parameters/wed_enable') || '');
    let wed = index(['Y', '1'], parameter) >= 0;
    let diagnostic = wedDiagnostics(wed);
    let configured = wedOption(readfile(MODULES));
    // No override: report the driver's existing default without writing it.
    if (configured == null) configured = wed;
    let bindings = 0, readable = false;
    for (let name in ['ppe0', 'ppe1']) {
        let raw = readfile('/sys/kernel/debug/' + name + '/bind');
        if (raw == null) continue;
        readable = true;
        for (let line in split(raw, '\n')) if (match(line, /[ \t]BND[ \t]/)) bindings++;
    }
    return {
        ok: true,
        configured: { software: section.flow_offloading == '1', hardware: section.flow_offloading_hw == '1', wed: configured },
        runtime: { software: active, hardware, wed: diagnostic.state == 'running' },
        wed_diagnostic: diagnostic,
        supported: { software: !!stat('/sys/module/nft_flow_offload') || !!stat('/lib/modules/' + trim(run('uname -r').text) + '/nft_flow_offload.ko'), hardware: !!stat('/sys/kernel/debug/ppe0') || !!stat('/sys/kernel/debug/ppe1'), wed: !!parameter },
        wed_pending: !!parameter && configured != wed,
        bindings: readable ? bindings : null,
        client_policies: policies(),
        clash_enabled: uci.get('openclash', 'config', 'enable') == '1'
    };
}
function validate(req, state) {
    for (let name in ['software', 'hardware', 'wed'])
        if (type(req[name]) != 'bool') die('开关参数无效');
    if (req.hardware && !req.software) die('硬件加速需要同时开启软件加速');
    for (let name in ['software', 'hardware', 'wed'])
        if (req[name] != state.configured[name] && !state.supported[name]) die('当前系统不支持这项加速');
    if (req.software && state.client_policies) die('请先取消客户端限速和黑名单，再开启流量加速');
}
function save(req) {
    let before = status();
    validate(req, before);
    let flowChanged = req.software != before.configured.software || req.hardware != before.configured.hardware;
    let wedChanged = req.wed != before.configured.wed;
    if (!flowChanged && !wedChanged) return before;
    if (length(uci.changes('firewall') || {})) die('防火墙有未保存的改动，请先处理后再应用');
    let firewall = readfile('/etc/config/firewall'), modules = readfile(MODULES), committed = false, moduleWritten = false;
    let section;
    uci.foreach('firewall', 'defaults', s => { if (!section) section = s['.name']; });
    try {
        if (flowChanged) {
            uci.set('firewall', section, 'flow_offloading', req.software ? '1' : '0');
            uci.set('firewall', section, 'flow_offloading_hw', req.hardware ? '1' : '0');
            uci.save('firewall');
            if (run('fw4 check >/tmp/tr3600-acceleration-check.log 2>&1').code != 0)
                die('防火墙检查失败，设置未应用');
            if (!uci.commit('firewall')) die('保存防火墙设置失败');
            committed = true;
            if (run('/etc/init.d/firewall reload >/tmp/tr3600-acceleration-check.log 2>&1').code != 0)
                die('防火墙应用失败，已恢复原设置');
            let after = status();
            if (after.runtime.software != req.software || after.runtime.hardware != req.hardware)
                die('加速状态未生效，已恢复原设置');
        }
        if (wedChanged) {
            if (!writefile(MODULES + '.tr3600-new', setWedOption(modules, req.wed))) die('保存 WED 设置失败');
            if (!rename(MODULES + '.tr3600-new', MODULES)) die('应用 WED 设置失败');
            moduleWritten = true;
        }
        return status();
    } catch (e) {
        uci.revert('firewall');
        if (committed) {
            writefile('/etc/config/firewall', firewall);
            uci.unload('firewall');
            run('/etc/init.d/firewall reload >/tmp/tr3600-acceleration-rollback.log 2>&1');
        }
        if (moduleWritten) { if (modules != null) writefile(MODULES, modules); else unlink(MODULES); }
        unlink(MODULES + '.tr3600-new');
        die(e.message || '应用失败');
    }
}
try {
    let mode = ARGV[0], result;
    if (mode == 'status') result = status();
    else if (mode == 'save') result = save(json(readfile('/dev/stdin') || '{}'));
    else if (mode == 'selftest') {
        let original = '# test\noptions other foo=bar\noptions mt7996e test=2 wed_enable=0 # retained\n';
        let enabled = setWedOption(original, true);
        if (!wedOption(enabled) || wedOption(setWedOption(enabled, false))) die('WED roundtrip failed');
        if (!match(enabled, /test=2/) || !match(enabled, /# retained/) || !match(enabled, /options other foo=bar/)) die('Module option preservation failed');
        if (wedOption('# options mt7996e wed_enable=1\n') != null) die('Comment parsing failed');
        if (setWedOption(enabled, true) != enabled) die('WED update not idempotent');
        let multiple = setWedOption('options mt7996e wed_enable=0\noptions mt7996e other=Y wed_enable=0\n', true);
        if (!wedOption(multiple) || !match(multiple, /other=Y/)) die('Duplicate override failed');
        if (wedHealth(true, false, true, 'failed to attach wed device') != 'failed') die('WED failure detection');
        if (wedHealth(true, true, true, 'failed to attach wed device') != 'running') die('WED recovery precedence');
        if (wedHealth(true, false, true, '') != 'not_attached') die('WED unattached detection');
        if (wedHealth(true, false, false, '') != 'unknown') die('WED unknown detection');
        if (wedHealth(false, false, true, 'failed to attach wed device') != 'disabled') die('WED disabled detection');
        result = { ok: true, tests: 11 };
    } else die('未知操作');
    print(sprintf('%J\n', result));
} catch (e) {
    print(sprintf('%J\n', { ok: false, message: e.message || '' + e }));
    exit(1);
}
