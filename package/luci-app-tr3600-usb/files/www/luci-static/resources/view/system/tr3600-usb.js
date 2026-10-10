'use strict';
'require view';
'require rpc';
'require poll';
'require ui';

var getStatus = rpc.declare({ object: 'tr3600.usb', method: 'status', expect: { '': {} } });
var configure = rpc.declare({ object: 'tr3600.usb', method: 'configure', params: ['device', 'metric'], expect: { '': {} } });
var disable = rpc.declare({ object: 'tr3600.usb', method: 'disable', expect: { '': {} } });
var reconnect = rpc.declare({ object: 'tr3600.usb', method: 'reconnect', expect: { '': {} } });

function link(path, text) {
	return E('a', { 'class': 'cbi-button cbi-button-action', href: L.url.apply(L, path.split('/')) }, text);
}
function table(headings, rows, empty) {
	return E('table', { 'class': 'table' }, [
		E('tr', { 'class': 'tr table-titles' }, headings.map(function(h) { return E('th', { 'class': 'th' }, h); }))
	].concat(rows.length ? rows.map(function(row) {
		return E('tr', { 'class': 'tr' }, row.map(function(c, i) { return E('td', { 'class': 'td', 'data-title': headings[i] }, c); }));
	}) : [E('tr', { 'class': 'tr' }, E('td', { 'class': 'td', colspan: headings.length }, empty))]));
}
function size(sectors) {
	var bytes = Number(sectors) * 512;
	return bytes >= 1073741824 ? (bytes / 1073741824).toFixed(1) + ' GiB' : (bytes / 1048576).toFixed(0) + ' MiB';
}

return view.extend({
	load: function() { return getStatus(); },
	render: function(data) {
		var state = data, busy = false;
		var devices = E('div'), disks = E('div'), support = E('div'), wan = E('div');
		var freshness = E('p', { 'class': 'cbi-section-description' });
		var notice = E('p');
		var select = E('select', { 'class': 'cbi-input-select', 'aria-label': 'USB 网络设备' });
		var metric = E('input', { 'class': 'cbi-input-text', type: 'number', min: 100, max: 900, value: data.wan.metric || '200', 'aria-label': 'USB 路由优先级' });
		var apply = E('button', { 'class': 'cbi-button cbi-button-apply', type: 'button' }, '启用 USB 上网');
		var off = E('button', { 'class': 'cbi-button cbi-button-neutral', type: 'button' }, '停用 USB 上网');
		var retry = E('button', { 'class': 'cbi-button cbi-button-neutral', type: 'button' }, '重新连接');
		var refresh = E('button', { 'class': 'cbi-button cbi-button-neutral', type: 'button' }, '刷新设备');
		var row = function(label, content) {
			return E('div', { 'class': 'cbi-value' }, [E('label', { 'class': 'cbi-value-title' }, label), E('div', { 'class': 'cbi-value-field' }, content)]);
		};
		var eligible = function(d) { return !d.owner || d.owner === 'usbwan'; };
		var buttons = function() {
			apply.disabled = busy || !state.networks.some(function(d) { return d.device === select.value && eligible(d); });
			off.disabled = busy || !state.wan.configured || state.wan.disabled === '1';
			retry.disabled = busy || !state.wan.configured || !state.networks.some(function(d) { return d.device === state.wan.device && eligible(d); });
			refresh.disabled = busy;
		};
		var update = function(d) {
			state = d;
			devices.replaceChildren(table(['USB 端口', '设备', '类型', '速率', '驱动'], d.devices.map(function(x) {
				return [x.port, (x.manufacturer ? x.manufacturer + ' ' : '') + (x.product || x.vidpid), x.type, x.speed ? x.speed + ' Mbps' : '未知', x.drivers || '未绑定驱动'];
			}), '未检测到外接 USB 设备'));
			disks.replaceChildren(table(['设备 / 分区', '容量', '文件系统', '挂载位置', '已用'], d.disks.map(function(x) {
				return [x.device + (x.partition ? '（分区）' : '（整盘）'), size(x.sectors), x.type || '未识别', x.mount || '未挂载', x.used || '—'];
			}), '没有 USB 块设备。若上方已检测到硬盘盒，请检查下方存储驱动状态。'));
			support.replaceChildren(table(['功能', '驱动状态', '对应软件包'], d.support.map(function(x) {
				return [x.name, x.available ? '内核驱动可用' : '缺少内核驱动', x.packages];
			}), '暂无信息'));
			var chosen = select.value || d.wan.device;
			select.replaceChildren.apply(select, d.networks.length ? d.networks.map(function(x) {
				return E('option', { value: x.device, disabled: !eligible(x) }, x.device + ' · ' + (x.driver || 'USB 网卡') + (eligible(x) ? '' : '（已用于 ' + x.owner + '）'));
			}) : [E('option', { value: '' }, '尚未检测到 USB 网卡')]);
			if (d.networks.some(function(x) { return x.device === chosen; })) select.value = chosen;
			wan.replaceChildren(
				row('USB 上网状态', !d.wan.configured ? '未配置' : d.wan.disabled === '1' ? '已停用' : d.wan.up ? '已连接' : '等待设备 / DHCP 地址'),
				row('当前 USB 接口', d.wan.device || '—'), row('IPv4 地址', d.wan.address || '—')
			);
			notice.textContent = d.networks.length ? '检测到 USB 网络设备。可作为 DHCP 上网出口，数字越大优先级越低。' : '当前没有可配置的 USB 网卡。Android 请开启“USB 网络共享”；iPhone 请开启“个人热点”并信任此设备。若仍未出现网卡，需要先补齐驱动。';
			freshness.textContent = '每 10 秒刷新 · 最近更新 ' + new Date().toLocaleTimeString();
			buttons();
		};
		var invoke = function(fn) {
			busy = true; buttons();
			return fn().then(function(r) {
				if (!r.ok) throw new Error(r.message || '操作失败');
				ui.addNotification(null, E('p', r.message), 'info');
				return getStatus().then(update);
			}).catch(function(e) { ui.addNotification(null, E('p', e.message), 'error'); })
			.finally(function() { busy = false; buttons(); });
		};
		apply.addEventListener('click', function() {
			var n = Number(metric.value);
			if (!Number.isInteger(n) || n < 100 || n > 900) {
				ui.addNotification(null, E('p', '优先级必须是 100–900 的整数。'), 'error'); return;
			}
			var selected = select.value;
			ui.showModal('启用 USB 上网', [
				E('p', {}, '将 ' + selected + ' 配置为独立 DHCP 出口 usbwan，并加入现有 WAN 防火墙区域。现有 WAN 优先，USB 路由优先级为 ' + n + '。'),
				E('p', {}, '手机共享网络可能消耗移动流量。这里只按路由优先级选择出口，不提供断网探测或多线路负载均衡。'),
				E('div', { 'class': 'right' }, [
					E('button', { 'class': 'cbi-button cbi-button-neutral', click: ui.hideModal }, '取消'), ' ',
					E('button', { 'class': 'cbi-button cbi-button-apply', click: function() { ui.hideModal(); invoke(function() { return configure(selected, String(n)); }); } }, '确认启用')
				])
			]);
		});
		off.addEventListener('click', function() { invoke(disable); });
		retry.addEventListener('click', function() { invoke(reconnect); });
		refresh.addEventListener('click', function() {
			busy = true; buttons();
			getStatus().then(update).catch(function(e) { ui.addNotification(null, E('p', e.message), 'error'); })
				.finally(function() { busy = false; buttons(); });
		});
		select.addEventListener('change', buttons);
		update(data);
		poll.add(function() {
			if (busy) return Promise.resolve();
			return getStatus().then(update).catch(function(e) { freshness.textContent = '刷新失败：' + e.message + '（显示上一次状态）'; });
		}, 10);
		return E('div', {}, [
			E('h2', {}, 'USB 设备与上网管理'),
			E('div', { 'class': 'cbi-section' }, [E('h3', {}, '已连接设备'), devices, E('p', {}, refresh), freshness]),
			E('div', { 'class': 'cbi-section' }, [E('h3', {}, '硬盘与文件共享'), disks,
				E('p', {}, '挂载与开机自动挂载在“挂载点”设置；挂载成功后可在“网络共享”添加 SMB 共享。'),
				E('p', {}, [link('admin/system/mounts', '管理挂载点'), ' ', link('admin/services/samba4', '管理网络共享')])]),
			E('div', { 'class': 'cbi-section' }, [E('h3', {}, '手机 USB 共享 / USB 网卡上网'), wan, notice,
				row('USB 网络设备', select), row('路由优先级', metric),
				E('p', {}, [apply, ' ', off, ' ', retry, ' ', link('admin/network/network', '详细接口设置')]),
				E('p', { 'class': 'cbi-section-description' }, '使用 DHCP 获取 IPv4 地址与 DNS。默认优先级 200；保持现有 WAN 优先。4G/5G 模块的 QMI、MBIM、串口拨号需另行安装协议支持。')]),
			E('div', { 'class': 'cbi-section' }, [E('h3', {}, '驱动与兼容性'),
				E('p', {}, '当前内核：' + data.kernel),
				support])
		]);
	},
	handleSaveApply: null,
	handleSave: null,
	handleReset: null
});
