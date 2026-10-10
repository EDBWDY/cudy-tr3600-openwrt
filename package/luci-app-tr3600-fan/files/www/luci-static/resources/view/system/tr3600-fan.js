'use strict';
'require view';
'require fs';
'require poll';
'require ui';

var backend = '/usr/libexec/tr3600-fan';
var modes = { auto: '自动温控', boost: '加强散热', full: '全速散热' };

function call(args) {
	return fs.exec(backend, args).then(function(r) {
		if (r.code !== 0) throw new Error(r.stderr || '读取风扇状态失败');
		return JSON.parse(r.stdout);
	});
}

return view.extend({
	load: function() { return call(['status']); },
	render: function(data) {
		var summary = E('div');
		var sensors = E('div');
		var freshness = E('p', { 'class': 'cbi-section-description' });
		var select = E('select', { 'class': 'cbi-input-select', 'aria-label': '散热模式' }, [
			E('option', { value: 'auto' }, '自动温控（固件默认曲线）'),
			E('option', { value: 'boost' }, '加强散热（提前升档）'),
			E('option', { value: 'full' }, '全速散热（持续 100% 输出）')
		]);
		select.value = data.mode;
		var button = E('button', { 'class': 'cbi-button cbi-button-apply', type: 'button' }, '应用并保存');
		var row = function(label, value) {
			return E('div', { 'class': 'cbi-value' }, [
				E('label', { 'class': 'cbi-value-title' }, label),
				E('div', { 'class': 'cbi-value-field' }, value)
			]);
		};
		var update = function(d) {
			summary.replaceChildren(
				row('当前模式', modes[d.mode] || d.mode),
				row('CPU 温度', (d.cpu_temp / 1000).toFixed(1) + ' °C'),
				row('风扇输出', Math.round(d.pwm / 255 * 100) + '%（PWM ' + d.pwm + '/255，档位 ' + d.state + '/4）'),
				row('内核温控', d.thermal_mode === 'enabled' && d.governor === 'step_wise' ? '已启用' : '异常，请检查'),
				row('实际升档阈值', d.mode === 'full' ? '全速持续输出' : d.thresholds.map(function(t) { return (t / 1000) + ' °C'; }).join(' / '))
			);
			sensors.replaceChildren.apply(sensors, d.sensors.map(function(s) {
				var names = { cpu_thermal: 'CPU', 'mdio_bus:01': '网口 PHY', 'mt7996_phy0.0': '2.4 GHz 无线', 'mt7996_phy0.1': '5 GHz 无线' };
				return row(names[s.name] || s.name, (s.temp / 1000).toFixed(1) + ' °C');
			}));
			freshness.textContent = '每 5 秒刷新 · 最近更新 ' + new Date().toLocaleTimeString();
		};
		button.addEventListener('click', function() {
			button.disabled = true;
			call(['set', select.value]).then(function(d) {
				update(d);
				ui.addNotification(null, E('p', '已保存散热模式，内核将在数秒内调整风扇。'), 'info');
			}).catch(function(e) {
				ui.addNotification(null, E('p', e.message), 'error');
			}).finally(function() { button.disabled = false; });
		});
		update(data);
		poll.add(function() {
			return call(['status']).then(update).catch(function(e) {
				freshness.textContent = '刷新失败：' + e.message + '（显示的是上一次读数）';
			});
		}, 5);
		return E('div', {}, [
			E('h2', {}, '散热风扇控制'),
			E('div', { 'class': 'cbi-section' }, [E('h3', {}, '实时状态'), summary, freshness]),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', {}, '散热模式'),
				E('p', {}, '自动：65 / 72 / 80 / 88 °C 升档；加强：55 / 62 / 70 / 78 °C 升档。模式保存后在开机时自动恢复。'),
				row('选择模式', E('div', {}, [select, ' ', button])),
				E('p', { 'class': 'cbi-section-description' }, '控制由内核温控完成，保留过热保护。百分比为 PWM 输出。')
			]),
			E('div', { 'class': 'cbi-section' }, [E('h3', {}, '温度传感器'), sensors])
		]);
	},
	handleSaveApply: null,
	handleSave: null,
	handleReset: null
});
