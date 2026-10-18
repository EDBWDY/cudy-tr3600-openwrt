/* SPDX-License-Identifier: GPL-3.0-only */
'use strict';
'require baseclass';
'require ui';

var confirmedWidgets = new WeakMap();

return baseclass.extend({
	confirmConeNat: function(option, sectionId, value) {
		var widget = option.getUIElement(sectionId);
		if (value !== '1' && value !== '2') {
			confirmedWidgets.delete(widget);
			return;
		}
		if (confirmedWidgets.get(widget) === value)
			return;

		// Dismissing the dialog must leave the feature disabled.
		widget.setValue('0');
		ui.showModal(_('UDP cone NAT security warning'), [
			E('p', {}, value === '2'
				? _('Enabling Full Cone NAT allows arbitrary external hosts to send packets through existing UDP mappings to internal devices. This increases exposure to unsolicited traffic and attacks. Enable it only when needed for games or P2P, and protect the internal devices.')
				: _('Address-restricted cone NAT allows previously contacted external IP addresses to send packets from any source port through existing UDP mappings. This is less restrictive than the system default NAT. Enable it only when needed.')),
			E('p', {}, _('These modes apply to IPv4 UDP only. TCP and other protocols keep system default NAT. Changing the mode clears existing IPv4 UDP state and may briefly reconnect UDP applications.')),
			E('p', {}, _('The feature stays disabled until you confirm. Save and apply the configuration to activate it.')),
			E('div', { 'class': 'right' }, [
				E('button', {
					'class': 'btn',
					'click': function() { ui.hideModal(); }
				}, _('Keep disabled')),
				' ',
				E('button', {
					'class': 'btn cbi-button-action',
					'click': function() {
						confirmedWidgets.set(widget, value);
						widget.setValue(value);
						ui.hideModal();
					}
				}, _('Understand the risk and continue'))
			])
		]);
	}
});
