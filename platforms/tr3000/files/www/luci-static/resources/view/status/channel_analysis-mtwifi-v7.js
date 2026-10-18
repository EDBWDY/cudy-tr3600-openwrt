'use strict';
'require view';
'require poll';
'require request';
'require network';
'require ui';
'require rpc';
'require tools.prng as random';

return view.extend({
	callGeometry: rpc.declare({object:'file', method:'exec', params:['command'], expect:{}}),
	callScan: rpc.declare({ object: 'iwinfo', method: 'scan', params: ['device'], expect: { results: [] } }),
	callFrequencyList: rpc.declare({
		object: 'iwinfo',
		method: 'freqlist',
		params: [ 'device' ],
		expect: { results: [] }
	}),

	callInfo: rpc.declare({
		object: 'iwinfo',
		method: 'info',
		params: [ 'device' ],
		expect: { }
	}),

	render_signal_badge(signalPercent, signalValue) {
		let icon, title, value;

		if (signalPercent < 0)
			icon = L.resource('icons/signal-none.svg');
		else if (signalPercent == 0)
			icon = L.resource('icons/signal-000-000.svg');
		else if (signalPercent < 25)
			icon = L.resource('icons/signal-000-025.svg');
		else if (signalPercent < 50)
			icon = L.resource('icons/signal-025-050.svg');
		else if (signalPercent < 75)
			icon = L.resource('icons/signal-050-075.svg');
		else
			icon = L.resource('icons/signal-075-100.svg');

		value = '%d\xa0%s'.format(signalValue, _('dBm'));
		title = '%s: %d %s'.format(_('Signal'), signalValue, _('dBm'));

		return E('div', {
			'class': 'ifacebadge',
			'title': title,
			'data-signal': signalValue
		}, [
			E('img', { 'src': icon }),
			value
		]);
	},

	add_wifi_to_graph(chan_analysis, res, scanCache, channels, channel_width) {
		scanCache[res.bssid].plot = {
			data: Object.assign({}, res), channels: channels.slice(), width: channel_width
		};
		if (chan_analysis.graph.offsetWidth <= 2 || chan_analysis.col_width <= 0)
			return;
		const offset_tbl = chan_analysis.offset_tbl;
		const height = chan_analysis.graph.clientHeight;
		const step = chan_analysis.col_width;
		const scale = chan_analysis.scale || { min: -100, max: -20 };
		const height_diff = res.local ? 36 : 70 + (scale.max - Math.max(scale.min, Math.min(scale.max, res.signal))) / (scale.max - scale.min) * (height - 70);

		if (scanCache[res.bssid].color == null)
			scanCache[res.bssid].color = random.derive_color(res.bssid);

		if (scanCache[res.bssid].graph == null || scanCache[res.bssid].graph === undefined) {
			const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
			const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
			const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
			const color = scanCache[res.bssid].color;

			line.setAttribute('style', 'fill:'+color+'4f'+';stroke:'+color+';stroke-width:0.5');
			text.setAttribute('style', 'fill:'+color+';font-size:9pt; font-family:sans-serif; text-shadow:1px 1px 1px #000');
			text.appendChild(document.createTextNode(res.ssid || res.bssid));

			group.setAttribute('clip-path', 'url(#' + chan_analysis.clipId + ')');
			group.appendChild(line);
			group.appendChild(text);

			chan_analysis.graph.firstElementChild.appendChild(group);
			scanCache[res.bssid].graph = { group : group, line : line, text : text };
		}

		channels.forEach(function(channel) {
			if (channel_width > 2) {
				if (!("main" in scanCache[res.bssid].graph)) {
					const main = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
					main.setAttribute('style', 'fill:url(#GradientVerticalCenteredBlack)');
					scanCache[res.bssid].graph.group.appendChild(main);

					scanCache[res.bssid].graph["main"] = main;
				}
				const main_offset = offset_tbl[res.channel];
				const points = [
					(main_offset-(step*(2  )))+','+height,
					(main_offset-(step*(2-1)))+','+height_diff,
					(main_offset+(step*(2-1)))+','+height_diff,
					(main_offset+(step*(2  )))+','+height
				];
				scanCache[res.bssid].graph.main.setAttribute('points', points);
			}

			const chan_offset = offset_tbl[channel];
			const points = [
				(chan_offset-(step*(channel_width  )))+','+height,
				(chan_offset-(step*(channel_width-1)))+','+height_diff,
				(chan_offset+(step*(channel_width-1)))+','+height_diff,
				(chan_offset+(step*(channel_width  )))+','+height
			];

			scanCache[res.bssid].graph.text.setAttribute('x', offset_tbl[res.channel]-step);
			scanCache[res.bssid].graph.text.setAttribute('y', height_diff - 2);
			scanCache[res.bssid].graph.line.setAttribute('points', res.primary_only ? [offset_tbl[res.channel]+','+height, offset_tbl[res.channel]+','+height_diff] : points);
			scanCache[res.bssid].graph.group.style.zIndex = res.signal*-1;
			scanCache[res.bssid].graph.group.style.opacity = res.stale ? '0.5' : null;
		})
		if (chan_analysis.axisLabels)
			chan_analysis.graph.firstElementChild.appendChild(chan_analysis.axisLabels);
	},

	resize_channel_graph(radio, force) {
		const graph = radio.graph;
		const width = graph.graph.offsetWidth;
		const height = graph.graph.offsetHeight;
		if (width <= 2 || height <= 2 || (!force && graph.width === width && graph.height === height))
			return;
		graph.width = width;
		graph.height = height;
		graph.graph.replaceChildren(graph.template.cloneNode(true));
        const svg = graph.graph.firstElementChild;
        svg.setAttribute('viewBox', '0 0 ' + graph.graph.clientWidth + ' ' + graph.graph.clientHeight);
        svg.style.overflow = 'visible';
        svg.querySelectorAll('line, text').forEach(node => node.remove());
        const clip = document.createElementNS('http://www.w3.org/2000/svg', 'clipPath');
        graph.clipId = 'channel-clip-' + radio.band + '-' + radio.dev.getName();
        clip.id = graph.clipId;
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', graph.graph.clientWidth); rect.setAttribute('height', graph.graph.clientHeight);
        clip.appendChild(rect); svg.appendChild(clip);
        const scale = graph.scale || { min: -100, max: -20 };
        graph.axisLabels = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        graph.axisLabels.setAttribute('class', 'channel-axis-labels');
        graph.axisLabels.setAttribute('pointer-events', 'none');
        svg.appendChild(graph.axisLabels);
        for (let i = 0; i <= 4; i++) {
            const value = scale.max - i * (scale.max - scale.min) / 4;
            const y = 70 + i * (graph.graph.clientHeight - 70) / 4;
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            for (const [k,v] of Object.entries({x1:0, x2:'100%', y1:y, y2:y, stroke:'#aab2bf', 'stroke-width':0.5})) line.setAttribute(k,v);
            svg.appendChild(line);
            const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            for (const [k,v] of Object.entries({x:-10, y:y+4, fill:'currentColor', 'font-size':12, 'text-anchor':'end'})) label.setAttribute(k,v);
            label.textContent = Number(value.toFixed(1));
            label.setAttribute('style', 'fill:currentColor;font-family:inherit');
            graph.axisLabels.appendChild(label);
        }
		graph.offset_tbl = {};
		this.create_channel_graph(graph, radio.channels, radio.band);
        const axisTitle = (text, x, y, rotate) => {
            const el = document.createElementNS('http://www.w3.org/2000/svg','text');
            el.textContent=text; el.setAttribute('x',x); el.setAttribute('y',y);
            el.setAttribute('style','fill:currentColor;font-size:13px;font-family:inherit;text-anchor:middle');
            if (rotate) el.setAttribute('transform','rotate(-90 '+x+' '+y+')');
            graph.axisLabels.appendChild(el);
        };
        axisTitle('信号强度 (dBm)', -58, graph.graph.clientHeight/2, true);
        axisTitle('Wi-Fi 信道', graph.graph.clientWidth/2, graph.graph.clientHeight+40);
        this.update_graph_theme(radio);
		for (const entry of Object.values(radio.scanCache)) {
			entry.graph = null;
			if (entry.plot)
				this.add_wifi_to_graph(graph, entry.plot.data, radio.scanCache,
					entry.plot.channels, entry.plot.width);
		}
	},


    update_graph_theme(radio) {
        let node = radio.graph.graph.parentElement, dark = false;
        while (node) {
            const rgb = getComputedStyle(node).backgroundColor.match(/[\d.]+/g);
            if (rgb && rgb.length >= 3 && (rgb.length < 4 || Number(rgb[3]) > 0.5)) {
                dark = Number(rgb[0])*0.2126 + Number(rgb[1])*0.7152 + Number(rgb[2])*0.0722 < 128;
                break;
            }
            node = node.parentElement;
        }
        radio.graph.graph.style.color = dark ? '#fff' : '#000';
        radio.graph.graph.style.backgroundColor = dark ? '#252525' : '#fff';
        radio.graph.graph.style.borderColor = dark ? '#777' : '#aaa';
    },
	bind_channel_graph(radio) {
        const recolor = () => requestAnimationFrame(() => this.update_graph_theme(radio));
        const themeObserver = new MutationObserver(recolor);
        themeObserver.observe(document.documentElement, {attributes:true, attributeFilter:['class','style']});
        themeObserver.observe(document.body, {attributes:true, attributeFilter:['class','style']});
        matchMedia('(prefers-color-scheme: dark)').addEventListener('change', recolor);
		const redraw = () => requestAnimationFrame(() => this.resize_channel_graph(radio, true));
		radio.graph.tab.addEventListener('cbi-tab-active', ev => {
			this.active_tab = ev.detail.tab;
			redraw();
			if (!radio.loadedOnce)
				poll.start();
		});
		if (typeof ResizeObserver !== 'undefined') {
			radio.graph.observer = new ResizeObserver(redraw);
			radio.graph.observer.observe(radio.graph.graph);
		}
		redraw();
	},

	create_channel_graph(chan_analysis, freq_tbl, band) {
		if (chan_analysis.graph.offsetWidth <= 2)
			return;
		const columns = (band != 2) ? freq_tbl.length * 4 : freq_tbl.length + 3;
		const chan_graph = chan_analysis.graph;
		const G = chan_graph.firstElementChild;
		const step = (chan_graph.offsetWidth - 2) / columns;
		let curr_offset = step;

		function createGraphHLine(graph, pos, width, dash) {
			const elem = document.createElementNS('http://www.w3.org/2000/svg', 'line');
			elem.setAttribute('x1', pos);
			elem.setAttribute('y1', 0);
			elem.setAttribute('x2', pos);
			elem.setAttribute('y2', '100%');
			elem.setAttribute('style', 'stroke:currentColor;opacity:0.25;stroke-width:'+width+';stroke-dasharray:'+dash);
			graph.appendChild(elem);
		}

		function createGraphText(graph, pos, text) {
			const elem = document.createElementNS('http://www.w3.org/2000/svg', 'text');
			elem.setAttribute('y', chan_graph.clientHeight + 20);
			elem.setAttribute('style', 'fill:currentColor;font-size:12px;font-family:inherit;text-anchor:middle');
			elem.setAttribute('x', pos);
			elem.appendChild(document.createTextNode(text));
			chan_analysis.axisLabels.appendChild(elem);
		}

		chan_analysis.col_width = step;

		createGraphHLine(G,curr_offset, 0.1, 1);
		for (let i=0; i< freq_tbl.length;i++) {
			const channel = freq_tbl[i]
			chan_analysis.offset_tbl[channel] = curr_offset+step;

			if (band != 2) {
				createGraphHLine(G,curr_offset+step, 0.1, 3);
				if (i % Math.max(1, Math.ceil(34 / (step*4))) === 0) createGraphText(G,curr_offset+step, channel);
			} else {
				createGraphHLine(G,curr_offset+step, 0.1, 0);
				if (i % Math.max(1, Math.ceil(24 / step)) === 0) createGraphText(G,curr_offset+step, channel);
			}
			curr_offset += step;

			if ((band != 2) && freq_tbl[i+1]) {
				const next_channel = freq_tbl[i+1];
				/* Check if we are transitioning to another 5/6Ghz band range */
				if ((next_channel - channel) == 4) {
					for (let j=1; j < 4; j++) {
						chan_analysis.offset_tbl[channel+j] = curr_offset+step;
						if (j == 2)
							createGraphHLine(G,curr_offset+step, 0.1, 0);
						else
							createGraphHLine(G,curr_offset+step, 0.1, 1);
						curr_offset += step;
					}
				} else {
					chan_analysis.offset_tbl[channel+1] = curr_offset+step;
					createGraphHLine(G,curr_offset+step, 0.1, 1);
					curr_offset += step;

					chan_analysis.offset_tbl[next_channel-2] = curr_offset+step;
					createGraphHLine(G,curr_offset+step, 0.5, 0);
					curr_offset += step;

					chan_analysis.offset_tbl[next_channel-1] = curr_offset+step;
					createGraphHLine(G,curr_offset+step, 0.1, 1);
					curr_offset += step;
				}
			}
		}
		createGraphHLine(G,curr_offset+step, 0.1, 1);


	},

    scanWithDeadline(task, milliseconds) {
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error('扫描请求超时')), milliseconds);
            Promise.resolve().then(task).then(value => {
                clearTimeout(timer); resolve(value);
            }, error => {
                clearTimeout(timer); reject(error);
            });
        });
    },

	handleScanRefresh() {
		if (!this.active_tab)
			return;

		const radio = this.radios[this.active_tab];
        if (radio.scanPending) return radio.scanPending;
		this.resize_channel_graph(radio);
		let q;

		radio.scanPending = this.scanWithDeadline(() => radio.dev.getWifiNetworks().then(nets => {
            const iface = nets.find(n => n.isUp() && n.getIfname());
            const device = iface ? iface.getIfname() : radio.dev.getName();
            return Promise.all([this.callScan(device), this.callInfo(device)]).then(pair => this.callGeometry('/usr/libexec/tr3000-channel-geometry').catch(() => ({})).then(detail => [...pair, detail]));
        }), 45000).then(L.bind(function([results, local_wifi, geometry]) {
			const table = radio.table;
			const chan_analysis = radio.graph;
			const scanCache = radio.scanCache;
			const band = radio.band;

			const rows = [];
            // mtwifi omits band and reports mhz=0 in scan entries.
            results = results.map(r => Object.assign({}, r, {band: r.band || (r.mhz >= 5925 ? 6 : r.mhz >= 4900 ? 5 : r.mhz >= 2400 ? 2 : Number(band))}));
            let actual = [], peers = [], channels = [];
            try { const detail = JSON.parse(geometry.stdout || '{}'); actual = detail.radios || []; peers = detail.peers || []; channels = detail.channels || []; } catch (_) {}
            for (const res of results) { const peer = peers.find(p => p.bssid === (res.bssid || '').toLowerCase()); if (peer) Object.assign(res, peer); }
            for (const res of results) {
                const detail = channels.find(p => p.bssid === (res.bssid || '').toLowerCase() && p.channel === res.channel);
                if (detail) res.driver_geometry = this.scanGeometry(detail);
            }
            const own = actual.find(r => r.band == band && r.channel == local_wifi.channel);
            if (!local_wifi.center_chan1 && own) local_wifi.center_chan1 = own.center;
            if (local_wifi.channel && !local_wifi.center_chan1) {
                local_wifi.center_chan1 = local_wifi.channel;
                local_wifi.primary_only = true;
            }
            const signals = results.filter(r => r.band == band && Number.isFinite(r.signal) && r.signal >= -110 && r.signal < 0).map(r => r.signal);
            const min = signals.length ? Math.max(-110, Math.floor((Math.min(...signals)-5)/10)*10) : -100;
            const max = signals.length ? Math.min(0, Math.max(min+20, Math.ceil((Math.max(...signals)+5)/10)*10)) : -20;
            chan_analysis.scale = { min, max };
            for (const key of Object.keys(scanCache)) {
                if (scanCache[key].data?.local) { scanCache[key].graph?.group.remove(); delete scanCache[key]; }
            }
            this.resize_channel_graph(radio, true);

			for (let res of results) {
				if (scanCache[res.bssid] == null)
					scanCache[res.bssid] = {};

				scanCache[res.bssid].data = res;
				scanCache[res.bssid].data.stale = false;
			}

			if (local_wifi.bssid && (local_wifi.frequency >= 5925 ? 6 : local_wifi.frequency >= 4900 ? 5 : 2) == band) {
				if (scanCache[local_wifi.bssid] == null)
					scanCache[local_wifi.bssid] = {};

				scanCache[local_wifi.bssid].data = local_wifi;

				if (chan_analysis.offset_tbl[local_wifi.channel] != null && local_wifi.center_chan1) {
					const center_channels = [local_wifi.center_chan1];
					const chan_width_text = local_wifi.htmode.replace(/[EV]*H[TE]/,''); /* Handle HT VHT HE EHT */
					let chan_width = local_wifi.primary_only ? 0 : parseInt(chan_width_text)/10;

					if (local_wifi.center_chan2) {
						center_channels.push(local_wifi.center_chan2);
						chan_width = 8;
					}

					local_wifi.signal = -10;
					local_wifi.local = true;
					local_wifi.ssid = 'Local Interface';

					this.add_wifi_to_graph(chan_analysis, local_wifi, scanCache, center_channels, chan_width);
					rows.push([
						'—',
						[
							E('span', { 'style': 'color:'+scanCache[local_wifi.bssid].color }, '⬤ '),
							local_wifi.ssid
						],
						'%d'.format(local_wifi.channel),
						'%h MHz'.format(chan_width_text),
						'%h'.format(local_wifi.mode),
						'%h'.format(local_wifi.bssid), this.technology(local_wifi), this.security(local_wifi)
					]);
				}
			}

			for (let k in scanCache)
				if (!scanCache[k].data.local && scanCache[k].data.stale)
					results.push(scanCache[k].data);

			results.sort(function(a, b) {
				if (a.channel - b.channel)
					return 1;

				if (a.ssid < b.ssid)
					return -1;
				else if (a.ssid > b.ssid)
					return 1;

				if (a.bssid < b.bssid)
					return -1;
				else if (a.bssid > b.bssid)
					return 1;
			});

			for (let res of results) {
				const qv = res.quality || 0;
				const qm = res.quality_max || 0;
				q = (qv > 0 && qm > 0) ? Math.floor((100 / qm) * qv) : 0;
				const s = res.stale ? 'opacity:0.5' : '';
				const center_channels = [res.channel];
				let chan_width = 2;

				/* Skip WiFi not supported by the current band */
				if (band != res.band)
					continue;
				if (chan_analysis.offset_tbl[res.channel] == null)
					continue;

				res.channel_width = "20 MHz";
				if (res.ht_operation != null) {
					/* Detect 40 MHz operation by looking for the presence of
					 * a secondary channel. */
					if (res.ht_operation.secondary_channel_offset == "below") {
						res.channel_width = "40 MHz";
						chan_width = 4; /* 40 MHz Channel Used */
						center_channels[0] -= 2;
					} else if (res.ht_operation.secondary_channel_offset == "above") {
						res.channel_width = "40 MHz";
						chan_width = 4; /* 40 MHz Channel Used */
						center_channels[0] += 2;
					} else {
						/* Fallback to 20 MHz due to discovery of other APs on the
						 * same channel (802.11n coexistence mechanism). */
						if (res.ht_operation.channel_width == 2040)
							res.channel_width = "20 MHz (40 MHz Intolerant)";
					}
				}

				/* if channel_width <= 40, refer to HT (above) for actual channel width,
				 * as vht_operation.channel_width == 40 really only means that the used
				 * bandwidth is <= 40 and could be 20 Mhz as well */
				if (res.vht_operation?.channel_width > 40) {
					center_channels[0] = res.vht_operation.center_freq_1;
					if (res.vht_operation.channel_width == 80) {
						chan_width = 8;
						res.channel_width = "80 MHz";

						/* If needed, adjust based on the 802.11ac Wave 2 interop workaround. */
						if (res.vht_operation.center_freq_2) {
							const diff = Math.abs(res.vht_operation.center_freq_2 -
							                    res.vht_operation.center_freq_1);

							if (diff == 8) {
								chan_width = 16;
								res.channel_width = "160 MHz";
								center_channels.push(res.vht_operation.center_freq_2);
							} else if (diff > 8) {
								chan_width = 8;
								res.channel_width = "80+80 MHz";
								center_channels.push(res.vht_operation.center_freq_2);
							}
						}
					} else if (res.vht_operation.channel_width == 8080) {
						res.channel_width = "80+80 MHz";
						chan_width = 8;
						center_channels.push(res.vht_operation.center_freq_2);
					} else if (res.vht_operation.channel_width == 160) {
						res.channel_width = "160 MHz";
						chan_width = 16;
					}
				}

				if (res.he_operation?.channel_width > 20) {
					center_channels[0] = res.he_operation.center_freq_1;
					chan_width = res.he_operation.channel_width / 10;
					switch (res.he_operation.channel_width) {
						case 40:
							res.channel_width = "40 MHz";
							break;
						case 80:
							res.channel_width = "80 MHz";
							break;
						case 160:
							res.channel_width = "160 MHz";
							center_channels.push(res.he_operation.center_freq_2);
							break;
					}
				}

				if (res.eht_operation?.channel_width == 320) {
					chan_width = 32;
					res.channel_width = "320 MHz";
					center_channels.push(res.eht_operation.center_freq_2);
				}

                const widthKnown = !!res.driver_geometry || !!(res.ht_operation || res.vht_operation || res.he_operation || res.eht_operation);
                res.primary_only = !widthKnown;
                if (!widthKnown) { res.channel_width = '—'; chan_width = 0; }
                if (res.driver_geometry) {
                    chan_width = res.driver_geometry.width / 10;
                    res.channel_width = res.driver_geometry.width + ' MHz';
                    center_channels.splice(0, center_channels.length, res.driver_geometry.center);
                }
				this.add_wifi_to_graph(chan_analysis, res, scanCache, center_channels, chan_width);

				rows.push([
					E('span', { 'style': s }, this.render_signal_badge(q, res.signal)),
					E('span', { 'style': s }, [
						E('span', { 'style': 'color:'+scanCache[res.bssid].color }, '⬤ '),
						(res.ssid != null) ? '%h'.format(res.ssid) : E('em', _('hidden'))
					]),
					E('span', { 'style': s }, '%d'.format(res.channel)),
					E('span', { 'style': s }, '%h'.format(res.channel_width)),
					E('span', { 'style': s }, '%h'.format(res.mode)),
					E('span', { 'style': s }, '%h'.format(res.bssid)), this.technology(res), this.security(res)
				]);

				scanCache[res.bssid].data.stale = true;
			}

			cbi_update_table(table, rows);

			if (!radio.loadedOnce) {
				radio.loadedOnce = true;
				poll.stop();
			}
		}, this)).catch(error => {
            poll.stop();
            const message = /timeout|timed out|超时/i.test(error.message || '')
                ? '扫描超时，请检查路由器连接后重新扫描'
                : '扫描失败：' + (error.message || String(error));
            cbi_update_table(radio.table, [], E('em', {}, message));
        }).finally(() => { radio.scanPending = null; });
        return radio.scanPending;
	},


    scanGeometry(r) {
        const ch = Number(r.channel), center = Number(r.center), vht = Number(r.vht);
        const delta = Math.abs(ch - center);
        if (!Number.isInteger(ch) || !Number.isInteger(center) || ch < 1 || center < 1) return null;
        if (vht === 0) {
            if (delta === 0) return {width:20, center};
            if (delta === 2) return {width:40, center};
        }
        if (ch > 14 && (vht === 1 || vht === 2)) {
            if ([50,114,163].includes(center) && [2,6,10,14].includes(delta)) return {width:160, center};
            if (vht === 1 && [42,58,106,122,138,155,171].includes(center) && [2,6].includes(delta)) return {width:80, center};
        }
        return null;
    },

    technology(r) {
        const modes = (r.technology || r.hwmode || '').toUpperCase().replace(/^11/, '').split('/');
        for (const mode of ['BE','AX','AC','N','G','B','A']) if (modes.includes(mode)) return mode;
        if (r.eht_operation) return 'BE';
        if (r.he_operation) return 'AX';
        if (r.vht_operation) return 'AC';
        if (r.ht_operation) return 'N';
        return '—';
    },
    security(r) {
        let versions=[], ciphers=[];
        if (r.security) {
            const raw=r.security.toUpperCase();
            if (/^(OPEN|NONE)(\/NONE)?$/.test(raw)) return '开放';
            for (const [token,label] of [['WPA3','WPA3-SAE'],['WPA2','WPA2-PSK'],['WPA1','WPA-PSK']])
                if (raw.includes(token)) versions.push(raw.includes('PSK') || raw.includes('SAE') ? label : token+'-EAP');
            if (!versions.length && raw.includes('WPA')) versions.push(raw.includes('PSK')?'WPA-PSK':'WPA-EAP');
            versions.reverse();
            ciphers=(raw.split('/')[1] || '').split('+');
            if (!versions.length) return raw;
        } else {
            const e=r.encryption;
            if (!e) return '—';
            if (e.enabled === false) return '开放';
            const auth=(e.authentication || []).map(a=>a.toLowerCase());
            versions=(e.wpa || []).map(v=>(v===1?'WPA':'WPA'+v)+'-'+(auth.includes('eap')?'EAP':v===3&&auth.includes('sae')?'SAE':'PSK'));
            ciphers=e.ciphers || [];
            if (!versions.length) return ciphers.join('/').toUpperCase() || '—';
        }
        const cipher=[...new Set(ciphers.filter(Boolean).map(c=>/^(CCMP|AES)$/i.test(c)?'AES':c.toUpperCase()))].join('/');
        return [...new Set(versions.map(v => v.replace(/-(PSK|SAE|EAP)$/, '')))].join('/');
    },
	radios: {},

	loadSVG(src) {
		return request.get(src).then(function(response) {
			if (!response.ok)
				throw new Error(response.statusText);

			return E('div', {
				'id': 'channel_graph',
				'style': 'width:100%;height:400px;border:1px solid #999;overflow:visible'
			}, E(response.text()));
		});
	},

	load() {
		return Promise.all([
			this.loadSVG(L.resource('svg/channel_analysis.svg')),
			network.getWifiDevices().then(L.bind(function(data) {
				const tasks = [], ret = [];

				for (let d of data) {
					ret[d.getName()] = { dev : d };

					tasks.push(this.callFrequencyList(d.getName())
					.then(L.bind(function(radio, data) {
						ret[radio.getName()].freq = data;
					}, this, d)));
				}

				return Promise.all(tasks).then(function() { return ret; })
			}, this))
		]);
	},

	render([svg, wifiDevs]) {
		const h2 = E('div', {'class' : 'cbi-title-section'}, [
			E('h2', {'class': 'cbi-title-field'}, [ _('Channel Analysis') ]),
			E('div', {'class': 'cbi-title-buttons'  }, [
				E('button', {
					'class': 'cbi-button cbi-button-edit',
					'click': ui.createHandlerFn(this, 'handleScanRefresh')
				}, [ _('Refresh Channels') ])])
			]);

		const tabs = E('div', {}, E('div'));

		for (let ifname in wifiDevs) {
			const bands = {
				[2] : { title: '2.4GHz', channels: [] },
				[5] : { title: '5GHz', channels: [] },
				[6] : { title: '6GHz', channels: [] },
			};

			/* Split FrequencyList in Bands */
			wifiDevs[ifname].freq.forEach(function(freq) {
				freq.band = freq.band || (freq.mhz >= 5925 ? 6 : freq.mhz >= 4900 ? 5 : freq.mhz >= 2400 ? 2 : 0);
				if (bands[freq.band])
					bands[freq.band].channels.push(freq.channel);
			});

			for (let band in bands) {
				if (bands[band].channels.length == 0 || (wifiDevs[ifname].dev.get('band') && wifiDevs[ifname].dev.get('band') != band + 'g'))
					continue;

				const csvg = svg.cloneNode(true);
				const table = E('table', { 'class': 'table' }, [
					E('tr', { 'class': 'tr table-titles' }, [
						E('th', { 'class': 'th col-2 middle center' }, _('Signal')),
						E('th', { 'class': 'th col-4 middle left' }, _('SSID')),
						E('th', { 'class': 'th col-2 middle center hide-xs' }, _('Channel')),
						E('th', { 'class': 'th col-3 middle left' }, _('Channel Width')),
						E('th', { 'class': 'th col-2 middle left hide-xs' }, _('Mode')),
						E('th', { 'class': 'th col-3 middle left hide-xs' }, _('BSSID')), E('th', { 'class': 'th' }, '技术'), E('th', { 'class': 'th' }, '加密')
					])
				]),
				tab = E('div', { 'data-tab': ifname+band, 'data-tab-title': ifname+' ('+bands[band].title+')' },
						[E('div', {style:'padding:18px 16px 52px 76px;overflow:visible'}, csvg),table,E('br')]),
				graph_data = {
					graph: csvg,
					template: csvg.firstElementChild.cloneNode(true),
					offset_tbl: {},
					col_width: 0,
					tab: tab,
				};

				this.radios[ifname+band] = {
					dev: wifiDevs[ifname].dev,
					band: band,
					channels: bands[band].channels,
					graph: graph_data,
					table: table,
					scanCache: {},
					loadedOnce: false,
				};

				cbi_update_table(table, [], E('em', { class: 'spinning' }, _('Starting wireless scan...')));

				tabs.firstElementChild.appendChild(tab)

				this.bind_channel_graph(this.radios[ifname+band]);
			}
		}

		ui.tabs.initTabGroup(tabs.firstElementChild.childNodes);

		this.pollFn = L.bind(this.handleScanRefresh, this);
		poll.add(this.pollFn);

		return E('div', {}, [h2, tabs]);
	},

	handleSaveApply: null,
	handleSave: null,
	handleReset: null
});
