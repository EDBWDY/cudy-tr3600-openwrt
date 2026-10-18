'use strict';
'require view';
'require poll';
'require tr3600_usb_status as usbStatus';

return view.extend({
	load: function() { return usbStatus.load(); },
	render: function(data) {
		var content = E('div', { 'class': 'cbi-section' }, usbStatus.render(data));
		poll.add(function() {
			return usbStatus.load().then(function(status) { content.replaceChildren(usbStatus.render(status)); });
		}, 10);
		return E('div', {}, [E('h2', {}, 'USB 状态'), content]);
	},
	handleSaveApply: null,
	handleSave: null,
	handleReset: null
});
