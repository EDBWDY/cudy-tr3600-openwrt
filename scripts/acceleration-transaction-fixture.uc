
let config, runtime, files, pending, checkFail, reloadFail, moduleFail, policiesCount, commits, reloads;
function reset() {
    config = { '.name': 'defaults', flow_offloading: '1', flow_offloading_hw: '1' };
    runtime = true;
    files = { '/etc/config/firewall': sprintf('%J', config), '/etc/modules.conf': '# keep\noptions other foo=1\n', '/sys/module/mt7996e/parameters/wed_enable': 'N', '/sys/kernel/debug/ppe0/bind': '00001 BND sample\n' };
    pending = {}; checkFail = false; reloadFail = false; moduleFail = false; policiesCount = 0; commits = 0; reloads = 0;
}
function readfile(path) { return files[path]; }
function writefile(path, text) { if (moduleFail && path == '/etc/modules.conf.tr3600-new') return false; files[path] = text; return length(text); }
function rename(from, to) { files[to] = files[from]; delete files[from]; return true; }
function unlink(path) { delete files[path]; return true; }
function stat(path) { return path == '/sys/module/nft_flow_offload' || path == '/sys/kernel/debug/ppe0' ? {} : null; }
function popen(cmd, mode) {
    let code = 0, text = '';
    if (index(cmd, 'nft list chain') == 0) text = runtime ? 'flow add @ft' : '';
    else if (index(cmd, 'nft list flowtable') == 0) text = runtime ? 'flags offload\n' : '';
    else if (index(cmd, 'fw4 check') == 0) code = checkFail ? 1 : 0;
    else if (index(cmd, '/etc/init.d/firewall reload') == 0) {
        reloads++;
        if (reloadFail && reloads == 1) code = 1;
        else runtime = config.flow_offloading == '1';
    } else if (cmd == 'uname -r') text = '6.12.94';
    return { read: () => text, close: () => code };
}
let uci = {
    foreach: (pkg, section, fn) => {
        if (pkg == 'firewall') fn(config);
        if (pkg == 'tr3600_clients' && policiesCount) fn({blocked:'1'});
    },
    get: () => '0',
    changes: () => pending,
    set: (pkg, section, key, value) => { config[key] = value; },
    save: () => { pending = {defaults:true}; return true; },
    commit: () => { files['/etc/config/firewall'] = sprintf('%J', config); pending = {}; commits++; return true; },
    revert: () => { config = json(files['/etc/config/firewall']); pending = {}; },
    unload: () => { config = json(files['/etc/config/firewall']); }
};
function assert(value, message) { if (!value) die(message); }
function rejected(req) { try { save(req); } catch (e) { return true; } return false; }

// ENGINE_INSERT

reset(); let original = files['/etc/config/firewall'];
assert(status().bindings == 1 && status().runtime.hardware, 'Real flow-table syntax');
assert(save({software:true,hardware:true,wed:false}).ok && commits == 0, 'No-op must not reload');
assert(rejected({software:false,hardware:true,wed:false}) && commits == 0, 'Invalid dependency');
policiesCount = 1;
assert(rejected({software:true,hardware:true,wed:false}) && commits == 0, 'Policy conflict');
reset(); checkFail = true;
assert(rejected({software:false,hardware:false,wed:false}) && files['/etc/config/firewall'] == original && runtime, 'Check failure must preserve state');
reset(); reloadFail = true;
assert(rejected({software:false,hardware:false,wed:true}) && files['/etc/config/firewall'] == original && runtime && !wedOption(files['/etc/modules.conf']), 'Reload rollback');
reset(); moduleFail = true;
assert(rejected({software:false,hardware:false,wed:true}) && files['/etc/config/firewall'] == original && runtime, 'Module-write rollback');
reset(); let result = save({software:false,hardware:false,wed:true});
assert(!result.runtime.software && !result.runtime.hardware && !result.runtime.wed && result.wed_pending, 'WED remains pending without reboot');
assert(match(files['/etc/modules.conf'], /options other foo=1/) && wedOption(files['/etc/modules.conf']), 'Unrelated options retained');
print('9 isolated backend transaction checks passed\n');
