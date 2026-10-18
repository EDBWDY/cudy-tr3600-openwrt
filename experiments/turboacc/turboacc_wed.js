'use strict';
'require baseclass';
'require form';
'require poll';
'require rpc';

var getWedStat = rpc.declare({ object: 'luci.turboacc', method: 'getWedStat', expect: { '': {} } });

return baseclass.extend({
    render: function(map) {
        return getWedStat().then(function(initial) {
            var section = map.section(form.TypedSection);
            section.anonymous = true;
            section.render = function() {
                var state = E('p'), error = E('p', { 'class': 'alert-message error' });
                var logs = E('pre', { 'style': 'white-space:pre-wrap;overflow-wrap:anywhere;max-height:18em;overflow:auto' });
                function update(value) {
                    var labels = {
                        attached: _('WED device attached; physical throughput is not measured here'),
                        disabled: _('WED is disabled'),
                        unavailable: _('The mt7996e WED parameter is unavailable'),
                        not_attached: _('WED was requested, but no wireless device attached'),
                        failed: _('WED initialization failed; see the error log')
                    };
                    state.textContent = (labels[value.health] || _('WED status unavailable')) +
                        (value.reboot_pending ? ' · ' + _('A reboot is required to apply the saved WED setting') : '');
                    var failed = value.health === 'failed' || value.health === 'not_attached';
                    error.textContent = value.apply_error || (failed ? labels[value.health] : '');
                    error.hidden = !error.textContent;
                    logs.textContent = value.log || _('No WED kernel messages');
                }
                update(initial);
                poll.add(function() { return getWedStat().then(update); }, 5);
                return E('fieldset', { 'class': 'cbi-section' }, [
                    E('legend', {}, _('WED wireless acceleration')),
                    state, error,
                    E('details', {}, [E('summary', {}, _('WED error log')), logs])
                ]);
            };
            if (initial.supported) {
                var settings = map.section(form.NamedSection, 'config', 'turboacc');
                var option = settings.option(form.Flag, 'wed_enable', _('Enable WED at next boot'),
                    _('Uses the paired MediaTek WED and mt76 driver. Saving never reloads Wi-Fi or reboots the router. Hardware forwarding still requires a controlled device test.'));
                option.default = '0';
                option.rmempty = false;
            }
            return map.render();
        });
    }
});
