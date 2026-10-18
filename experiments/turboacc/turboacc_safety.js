/* SPDX-License-Identifier: GPL-3.0-only */
'use strict';
'require ui';

var confirmedWidgets = new WeakSet();

return {
	confirmFullCone: function(option, sectionId, value) {
		var widget = option.getUIElement(sectionId);
		if (value !== '2') {
			confirmedWidgets.delete(widget);
			return;
		}
		if (confirmedWidgets.has(widget))
			return;

		// Dismissing the dialog must leave the feature disabled.
		widget.setValue('0');
		ui.showModal(_('Full Cone NAT security warning'), [
			E('p', {}, _('Enabling Full Cone NAT allows arbitrary external hosts to send packets through existing UDP mappings to internal devices. This increases exposure to unsolicited traffic and attacks. Enable it only when needed for games or P2P, and protect the internal devices.')),
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
						confirmedWidgets.add(widget);
						widget.setValue('2');
						ui.hideModal();
					}
				}, _('Understand the risk and continue'))
			])
		]);
	}
};
