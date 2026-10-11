'use strict';
'require view';
'require rpc';
'require poll';
'require ui';

var getStatus = rpc.declare({ object: 'tr3600.acceleration', method: 'status', expect: {} });
var saveSettings = rpc.declare({ object: 'tr3600.acceleration', method: 'save', params: ['software', 'hardware', 'wed'], expect: {} });
function darkTheme() {
    var rgb = getComputedStyle(document.body).backgroundColor.match(/[\d.]+/g);
    return !!(rgb && rgb.length >= 3 && Number(rgb[0]) * .2126 + Number(rgb[1]) * .7152 + Number(rgb[2]) * .0722 < 128);
}
function values(inputs) {
    return { software: inputs.software.checked, hardware: inputs.hardware.checked, wed: inputs.wed.checked };
}
function same(a, b) { return ['software', 'hardware', 'wed'].every(function(k) { return !!a[k] === !!b[k]; }); }

return view.extend({
    load: function() { return getStatus(); },
    handleSave: null, handleSaveApply: null, handleReset: null,
    update: function(data, reset) {
        var self = this;
        if (!data.ok) throw new Error(data.message || '读取加速状态失败');
        reset = reset || !this.data || same(values(this.inputs), this.data.configured);
        this.data = data;
        this.root.dataset.accDark = darkTheme() ? 'true' : 'false';
        ['software', 'hardware', 'wed'].forEach(function(k) {
            if (reset) self.inputs[k].checked = !!data.configured[k];
            self.inputs[k].disabled = self.busy || !L.hasViewPermission() || !data.supported[k];
            var enabled = data.runtime[k], pending = k === 'wed' && data.wed_pending;
            self.badges[k].textContent = !data.supported[k] ? '不支持' : pending ? '待重启' : enabled ? '已开启' : '已关闭';
            self.badges[k].className = 'acc-badge ' + (pending ? 'acc-pending' : enabled ? 'acc-on' : 'acc-off');
            self.runtime[k].textContent = '当前状态 · ' + (enabled ? '开启' : '关闭');
            self.runtime[k].hidden = !pending;
        });
        this.summary.textContent = data.runtime.hardware ? '硬件加速运行中' : data.runtime.software ? '软件加速运行中' : '常规转发';
        this.count.textContent = data.bindings == null ? '—' : String(data.bindings);
        this.countLabel.textContent = data.bindings === 0 ? '硬件连接 · 等待流量' : '硬件连接';
        var notes = [];
        if (data.runtime.software) notes.push(E('div', {}, '加速已开启，客户端流量统计可能不准确'));
        if (data.client_policies) notes.push(E('div', {}, '有客户端限速或黑名单，取消后才能开启流量加速'));
        if (data.clash_enabled) notes.push(E('div', {}, 'OpenClash 正在启用，加速后的代理分流需要实际确认'));
        if (data.wed_pending) notes.push(E('div', {}, 'WED 设置已保存，下次重启生效'));
        this.notes.replaceChildren.apply(this.notes, notes);
        this.notes.hidden = !notes.length;
        this.changed();
    },
    changed: function() {
        var dirty = !same(values(this.inputs), this.data.configured);
        this.apply.disabled = this.busy || !L.hasViewPermission() || !dirty;
        this.reset.disabled = this.busy || !dirty;
        this.dirty.textContent = dirty ? '有未应用的改动' : '';
    },
    applySettings: function() {
        var self = this, requested = values(this.inputs);
        this.busy = true;
        this.error.textContent = '';
        this.update(this.data, false);
        this.apply.textContent = '正在应用…';
        return saveSettings(requested.software, requested.hardware, requested.wed).then(function(r) {
            if (!r.ok) throw new Error(r.message || '应用失败');
            self.update(r, true);
            ui.addNotification(null, E('p', {}, r.wed_pending ? '设置已保存，WED 下次重启生效' : '加速设置已应用'), 'info');
        }).catch(function(e) {
            self.error.textContent = e.message || '应用失败';
            return getStatus().then(function(r) { self.update(r, false); });
        }).finally(function() {
            self.busy = false;
            self.apply.textContent = '保存并应用';
            self.update(self.data, false);
        });
    },
    render: function(data) {
        var self = this;
        this.inputs = {}; this.badges = {}; this.runtime = {}; this.busy = false;
        this.summary = E('strong', { 'class': 'acc-summary-title' });
        this.count = E('strong', { 'class': 'acc-count' });
        this.countLabel = E('span', { 'class': 'acc-muted' }, '硬件连接');
        this.notes = E('div', { 'class': 'acc-notes' });
        this.error = E('div', { 'class': 'acc-error', 'role': 'alert' });
        this.dirty = E('span', { 'class': 'acc-muted' });
        function row(key, title, subtitle) {
            var input = self.inputs[key] = E('input', { 'type': 'checkbox', 'aria-label': title, 'change': function() {
                if (key === 'hardware' && input.checked) self.inputs.software.checked = true;
                if (key === 'software' && !input.checked) self.inputs.hardware.checked = false;
                self.changed();
            } });
            var badge = self.badges[key] = E('span', { 'class': 'acc-badge' });
            var runtime = self.runtime[key] = E('span', { 'class': 'acc-muted acc-runtime' });
            return E('section', { 'class': 'acc-card' }, [
                E('div', { 'class': 'acc-info' }, [
                    E('h3', {}, title),
                    E('div', { 'class': 'acc-subtitle' }, subtitle),
                    runtime
                ]),
                E('div', { 'class': 'acc-control' }, [badge, E('label', { 'class': 'acc-switch' }, [input, E('span', { 'class': 'acc-track' }), E('span', { 'class': 'acc-sr' }, title)])])
            ]);
        }
        this.apply = E('button', { 'class': 'cbi-button cbi-button-positive', 'click': function() { return self.applySettings(); } }, '保存并应用');
        this.reset = E('button', { 'class': 'cbi-button', 'click': function() { self.error.textContent = ''; self.update(self.data, true); } }, '撤销改动');
        this.root = E('div', { 'class': 'acc-page' }, [
            E('link', { 'rel': 'stylesheet', 'href': L.resource('tr3600-acceleration.css?v=1.0.1') }),
            E('div', { 'class': 'acc-heading' }, E('h2', {}, '硬件加速')),
            E('div', { 'class': 'acc-panel' }, [
                E('div', { 'class': 'acc-summary' }, [this.summary,
                    E('div', { 'class': 'acc-metric' }, [this.countLabel, this.count])]),
                row('software', '软件加速', '减少 CPU 转发开销'),
                row('hardware', '硬件加速', 'MediaTek PPE'),
                row('wed', '无线加速', 'WED · 重启后生效'),
                this.notes, this.error,
                E('div', { 'class': 'acc-actions' }, [this.dirty, E('div', {}, [this.reset, this.apply])])
            ])
        ]);
        this.update(data, true);
        poll.add(function() {
            if (self.busy) return;
            return getStatus().then(function(r) { self.update(r, false); }).catch(function(e) { self.error.textContent = e.message || '读取状态失败'; });
        }, 7);
        return this.root;
    }
});
