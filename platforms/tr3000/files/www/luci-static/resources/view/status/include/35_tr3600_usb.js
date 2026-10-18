'use strict';
'require baseclass';
'require tr3600_usb_status as usbStatus';

return baseclass.extend({
	title: 'USB 状态',
	load: function() { return usbStatus.load(); },
	render: function(data) { return usbStatus.render(data); }
});
