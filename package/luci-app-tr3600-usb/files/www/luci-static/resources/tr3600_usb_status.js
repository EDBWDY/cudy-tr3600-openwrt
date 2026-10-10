'use strict';
'require baseclass';
'require rpc';

var callStatus = rpc.declare({ object: 'tr3600.usb', method: 'status', expect: { '': {} } });

function table(headings, rows, empty) {
	return E('table', { 'class': 'table' }, [
		E('tr', { 'class': 'tr table-titles' }, headings.map(function(h) { return E('th', { 'class': 'th' }, h); }))
	].concat(rows.length ? rows.map(function(row) {
		return E('tr', { 'class': 'tr' }, row.map(function(cell, index) {
			return E('td', { 'class': 'td', 'data-title': headings[index] }, cell);
		}));
	}) : [E('tr', { 'class': 'tr' }, E('td', { 'class': 'td', colspan: headings.length }, empty))]));
}

function capacity(sectors) {
	var bytes = Number(sectors) * 512;
	return Number.isFinite(bytes) && bytes > 0 ? (bytes / 1073741824).toFixed(1) + ' GiB' : '—';
}

function speed(value) {
	var mbps = Number(value);
	return mbps > 0 ? (mbps >= 1000 ? mbps / 1000 + ' Gbps' : mbps + ' Mbps') : '—';
}

return baseclass.extend({
	title: 'USB 状态',
	load: function() { return callStatus().catch(function() { return { ok: false }; }); },
	render: function(data) {
		if (!data || !data.ok) return E('p', {}, '暂时无法读取 USB 状态');
		var devices = data.devices || [], disks = data.disks || [], wan = data.wan || {};
		var partitions = disks.filter(function(d) { return d.partition || d.type || d.mount; });
		if (!partitions.length) partitions = disks;
		var wanState = !wan.configured ? '未配置' : wan.disabled === '1' ? '已停用' : wan.up ? '已连接' : '等待设备 / 地址';
		return E('div', {}, [
			E('p', {}, '已连接 ' + devices.length + ' 个 USB 设备'),
			table(['设备', '端口', '连接速率', '驱动'], devices.map(function(d) {
				return [(d.manufacturer ? d.manufacturer + ' ' : '') + (d.product || d.vidpid || 'USB 设备'),
					d.port || '—', speed(d.speed), d.drivers || '—'];
			}), '暂无外接 USB 设备'),
			E('h4', { style: 'margin: 1em 16px 0.5em' }, '硬盘与挂载'),
			table(['分区', '容量', '文件系统', '挂载位置', '已用'], partitions.map(function(d) {
				return [d.device, capacity(d.sectors), d.type || '—', d.mount || '未挂载', d.used || '—'];
			}), '暂无 USB 硬盘'),
			E('h4', { style: 'margin: 1em 16px 0.5em' }, 'USB 上网'),
			table(['状态', '网络接口', 'IPv4 地址'], [[wanState, wan.device || '—', wan.address || '—']], ''),
			E('p', {}, [
				E('a', { 'class': 'cbi-button cbi-button-action', href: L.url('admin', 'system', 'tr3600_usb') }, 'USB 管理'), ' ',
				E('a', { 'class': 'cbi-button cbi-button-action', href: L.url('admin', 'system', 'mounts') }, '管理挂载点')
			])
		]);
	}
});
