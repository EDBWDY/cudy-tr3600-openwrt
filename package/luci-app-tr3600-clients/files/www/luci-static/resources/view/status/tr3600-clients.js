'use strict';
'require view';
'require rpc';
'require poll';
'require ui';

var status = rpc.declare({ object: 'tr3600.clients', method: 'status', expect: {} });
var save = rpc.declare({ object: 'tr3600.clients', method: 'save', params: ['mac', 'alias', 'blocked', 'upload', 'download'], expect: {} });
function bytes(n) {
    n = Math.max(0, Number(n) || 0);
    var units = ['B', 'KB', 'MB', 'GB', 'TB'], i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return n.toFixed(i ? (n >= 100 ? 0 : 1) : 0) + ' ' + units[i];
}
function rate(n) { return ((Number(n) || 0) * 8 / 1000000).toFixed(2) + ' Mbps'; }
function darkTheme() {
    var rgb = getComputedStyle(document.body).backgroundColor.match(/[\d.]+/g);
    return !!(rgb && rgb.length >= 3 && Number(rgb[0]) * .2126 + Number(rgb[1]) * .7152 + Number(rgb[2]) * .0722 < 128);
}
function icon(text, cls) { return E('span', { 'class': 'cm-icon ' + (cls || '') }, text); }

return view.extend({
    load: function() { return status(); },
    handleSaveApply: null, handleSave: null, handleReset: null,
    edit: function(d) {
        var self = this, p = d.policy || {}, locked = !L.hasViewPermission();
        var alias = E('input', { 'class': 'cbi-input-text', 'type': 'text', 'maxlength': 64, 'value': p.alias || '', 'placeholder': d.name || '例如：客厅电视' });
        var upload = E('input', { 'class': 'cbi-input-text', 'type': 'number', 'min': 0, 'max': 2500, 'step': 1, 'value': p.upload || 0 });
        var download = E('input', { 'class': 'cbi-input-text', 'type': 'number', 'min': 0, 'max': 2500, 'step': 1, 'value': p.download || 0 });
        var blocked = E('input', { 'type': 'checkbox', 'checked': p.blocked ? true : null });
        var accelerated = !!(this.data && this.data.offloading && this.data.offloading.active);
        upload.disabled = download.disabled = blocked.disabled = locked || accelerated;
        var error = E('p', { 'class': 'cm-error' });
        function field(label, input) { return E('label', { 'class': 'cm-field' }, [E('span', {}, label), input]); }
        var button = E('button', { 'class': 'cbi-button cbi-button-positive', 'disabled': locked ? true : null, 'click': function() {
            var up = Number(upload.value), down = Number(download.value);
            if (![up, down].every(function(n) { return Number.isInteger(n) && (n === 0 || n >= 1 && n <= 2500); })) {
                error.textContent = '请输入 1–2500 的整数 Mbps，或填 0 取消限速。'; return;
            }
            button.disabled = true; error.textContent = '';
            return save(d.mac, alias.value, blocked.checked, up, down).then(function(r) {
                if (!r.ok) throw new Error(r.message || '保存失败');
                ui.hideModal();
                return status().then(function(data) { self.data = data; self.paint(); });
            }).catch(function(e) { error.textContent = e.message; }).finally(function() { button.disabled = locked; });
        } }, '保存');
        ui.showModal('管理设备', [
            E('div', { 'class': 'cm-edit', 'data-cm-dark': darkTheme() ? 'true' : 'false' }, [
                E('p', { 'class': 'cm-muted' }, d.mac + ' · ' + (d.addresses || []).join(' / ')),
                field('设备别名', alias),
                E('div', { 'class': 'cm-edit-grid' }, [field('上传上限 · Mbps', upload), field('下载上限 · Mbps', download)]),
                E('p', { 'class': 'cm-muted' }, '0 表示不限速'),
                accelerated ? E('p', { 'class': 'cm-muted' }, '关闭流量分载后可设置限速和黑名单') : '',
                E('label', { 'class': 'cm-block-toggle' }, [blocked, E('span', {}, '加入黑名单，禁止该设备上网')]),
                error
            ]),
            E('div', { 'class': 'right' }, [E('button', { 'class': 'cbi-button', 'click': ui.hideModal }, '取消'), ' ', button])
        ]);
    },
    paint: function() {
        var self = this, data = this.data || {}, all = data.clients || [];
        var accelerated = !!(data.offloading && data.offloading.active);
        if (this.root) this.root.dataset.cmDark = darkTheme() ? 'true' : 'false';
        var expanded = {};
        this.cards.querySelectorAll('details[open]').forEach(function(el) { expanded[el.dataset.mac] = true; });
        var query = this.search.value.trim().toLowerCase(), filtered = all.filter(function(d) {
            return (!self.filter || (self.filter === 'online' ? d.online : d.policy.blocked)) &&
                [d.mac, d.name, d.policy.alias].concat(d.addresses || []).join(' ').toLowerCase().indexOf(query) >= 0;
        });
        filtered.sort(function(a, b) {
            return Number(b.online) - Number(a.online) || a.mac.localeCompare(b.mac);
        });
        var up = 0, down = 0, total = 0;
        all.forEach(function(d) { up += d.up_rate || 0; down += d.down_rate || 0; total += (d.up_bytes || 0) + (d.down_bytes || 0); });
        function metric(label, value, sub) { return E('div', { 'class': 'cm-metric' }, [E('span', {}, label), E('strong', {}, value), E('small', {}, sub)]); }
        this.summary.replaceChildren(
            metric('当前在线', '' + all.filter(function(d) { return d.online; }).length, '共发现 ' + all.length + ' 台设备'),
            metric('↓ 总下载', rate(down), '最近一次采样'),
            metric('↑ 总上传', rate(up), '最近一次采样'),
            metric('累计流量', bytes(total), '本次统计服务启动以来')
        );
        this.health.textContent = data.error || (data.stale ? '数据暂未更新，请检查客户端管理服务。' :
            accelerated ? (data.offloading.hardware ? '硬件加速已开启，流量统计可能不准确' : '流量分载已开启，流量统计可能不准确') : '');
        this.health.style.display = this.health.textContent ? '' : 'none';
        this.updated.textContent = data.time ? '每 5 秒更新 · ' + new Date(data.time * 1000).toLocaleTimeString() : '等待采样';
        var cards = filtered.map(function(d) {
            var p = d.policy, state = p.blocked ? (accelerated ? '已设黑名单' : '已拉黑') : d.online ? '在线' : '离线';
            var name = p.alias || d.name || '未命名设备';
            var ipv4 = (d.addresses || []).filter(function(ip) { return ip.indexOf(':') < 0; });
            var ipv6 = (d.addresses || []).filter(function(ip) { return ip.indexOf(':') >= 0; });
            var tags = [E('span', { 'class': 'cm-pill ' + (p.blocked ? 'cm-red' : d.online ? 'cm-green' : '') }, state)];
            if (d.connection && d.connection !== '未确认') tags.push(E('span', { 'class': 'cm-pill' }, d.connection + (d.protocol ? ' · ' + d.protocol : '')));
            if (d.signal != null) tags.push(E('span', { 'class': 'cm-pill' }, d.signal + ' dBm'));
            if (p.upload || p.download) tags.push(E('span', { 'class': 'cm-pill cm-purple' }, accelerated ? '限速可能不生效' : '限速中'));
            return E('article', { 'class': 'cm-card' + (p.blocked ? ' cm-blocked' : '') }, [
                E('div', { 'class': 'cm-card-head' }, [icon(name.slice(0, 1).toUpperCase()), E('div', { 'class': 'cm-name' }, [E('h3', {}, name), E('small', {}, d.mac)]), E('button', { 'class': 'cm-manage', 'click': function() { self.edit(d); } }, '管理')]),
                E('div', { 'class': 'cm-tags' }, tags),
                E('div', { 'class': 'cm-ip' }, [E('span', {}, 'IPv4'), E('strong', {}, ipv4.join(' · ') || '未获取')]),
                E('details', { 'class': 'cm-ipv6', 'data-mac': d.mac, 'open': expanded[d.mac] || null }, [E('summary', {}, 'IPv6 · ' + ipv6.length + ' 个地址'), E('div', {}, ipv6.length ? ipv6.map(function(ip) { return E('div', {}, ip); }) : '未获取')]),
                E('div', { 'class': 'cm-traffic' }, [E('div', { 'class': 'cm-speeds' }, [E('div', {}, [E('small', {}, '↓ 下载'), E('strong', {}, rate(d.down_rate)), E('span', {}, '累计下载 ' + bytes(d.down_bytes))]), E('div', {}, [E('small', {}, '↑ 上传'), E('strong', {}, rate(d.up_rate)), E('span', {}, '累计上传 ' + bytes(d.up_bytes))])]),
                E('div', { 'class': 'cm-traffic-total' }, [E('span', {}, '总流量'), E('strong', {}, bytes((d.down_bytes || 0) + (d.up_bytes || 0)))])]),
                E('div', { 'class': 'cm-card-foot' }, p.blocked ? (accelerated ? '加速已开启，黑名单可能不生效' : '已禁止上网') : (p.upload || p.download ? (accelerated ? '加速已开启，限速可能不生效' : '上限：↑ ' + (p.upload ? p.upload + ' Mbps' : '不限') + ' / ↓ ' + (p.download ? p.download + ' Mbps' : '不限')) : '访问正常 · 不限速'))
            ]);
        });
        this.cards.replaceChildren.apply(this.cards, cards.length ? cards : [E('div', { 'class': 'cm-empty' }, '没有符合条件的设备')]);
    },
    render: function(data) {
        ui.menu.flushCache();
        var self = this;
        this.data = data; this.filter = '';
        this.summary = E('div', { 'class': 'cm-summary' });
        this.cards = E('div', { 'class': 'cm-cards' });
        this.health = E('div', { 'class': 'cm-health' });
        this.updated = E('span', { 'class': 'cm-muted' });
        this.search = E('input', { 'class': 'cbi-input-text cm-search', 'type': 'search', 'placeholder': '搜索名称、IP 或 MAC', 'input': function() { self.paint(); } });
        var select = E('select', { 'class': 'cbi-input-select cm-device-filter', 'aria-label': '筛选设备', 'change': function() { self.filter = this.value; self.paint(); } }, [E('option', { value: '' }, '全部设备'), E('option', { value: 'online' }, '在线设备'), E('option', { value: 'blocked' }, '黑名单')]);
        var root = E('div', { 'class': 'cm-root' }, [
            E('link', { 'rel': 'stylesheet', 'href': L.resource('tr3600-clients.css') + '?v=1.0.16' }),
            E('div', { 'class': 'cm-heading' }, [E('div', {}, [E('h2', {}, '客户端管理'), E('p', { 'class': 'cm-muted' }, '查看连接，管理每台设备的网络使用。')]), this.updated]),
            this.health, this.summary,
            E('div', { 'class': 'cm-toolbar' }, [this.search, select]), this.cards
        ]);
        this.root = root;
        this.paint();
        poll.add(function() { return status().then(function(data) { self.data = data; self.paint(); }).catch(function(e) { self.health.style.display = ''; self.health.textContent = '读取失败：' + e.message; }); }, 5);
        return root;
    }
});
