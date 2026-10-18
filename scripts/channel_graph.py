"""Size channel graphs only while visible, and redraw them after tab/size changes."""
import json

VIEW_NAME = 'channel_analysis-tr3600-v6.js'


def customize_view(text):
    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise RuntimeError('Pinned channel-analysis source layout changed: ' + old[:70])
        text = text.replace(old, new)

    replace('\t\tconst offset_tbl = chan_analysis.offset_tbl;', '''		scanCache[res.bssid].plot = {
			data: Object.assign({}, res), channels: channels.slice(), width: channel_width
		};
		if (chan_analysis.graph.offsetWidth <= 2 || chan_analysis.col_width <= 0)
			return;
		const offset_tbl = chan_analysis.offset_tbl;''')
    old_listener = '''		chan_analysis.tab.addEventListener('cbi-tab-active', L.bind(function(ev) {
			this.active_tab = ev.detail.tab;
			if (!this.radios[this.active_tab].loadedOnce)
				poll.start();
		}, this));'''
    replace(old_listener, '')
    replace('\tcreate_channel_graph(chan_analysis, freq_tbl, band) {', '''	resize_channel_graph(radio) {
		const graph = radio.graph;
		const width = graph.graph.offsetWidth;
		const height = graph.graph.offsetHeight;
		if (width <= 2 || height <= 2 || (graph.width === width && graph.height === height))
			return;
		graph.width = width;
		graph.height = height;
		graph.graph.replaceChildren(graph.template.cloneNode(true));
		graph.offset_tbl = {};
		this.create_channel_graph(graph, radio.channels, radio.band);
		for (const entry of Object.values(radio.scanCache)) {
			entry.graph = null;
			if (entry.plot)
				this.add_wifi_to_graph(graph, entry.plot.data, radio.scanCache,
					entry.plot.channels, entry.plot.width);
		}
	},

	bind_channel_graph(radio) {
		const redraw = () => requestAnimationFrame(() => this.resize_channel_graph(radio));
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
			return;''')
    replace('\t\tconst radio = this.radios[this.active_tab];', '\t\tconst radio = this.radios[this.active_tab];\n\t\tthis.resize_channel_graph(radio);')
    replace('\t\t\t\t\tgraph: csvg,', '\t\t\t\t\tgraph: csvg,\n\t\t\t\t\ttemplate: csvg.firstElementChild.cloneNode(true),')
    replace('\t\t\t\t\tband: band,', '\t\t\t\t\tband: band,\n\t\t\t\t\tchannels: bands[band].channels,')
    replace('\t\t\t\trequestAnimationFrame(L.bind(this.create_channel_graph, this, graph_data, bands[band].channels, band));', '\t\t\t\tthis.bind_channel_graph(this.radios[ifname+band]);')
    from channel_axes import external_axes
    from channel_details import add_details
    return add_details(external_axes(improve_view(text)))


def customize_package(package):
    from channel_details import install_helper
    install_helper(package)
    original = package / 'htdocs/luci-static/resources/view/status/channel_analysis.js'
    original.with_name(VIEW_NAME).write_text(customize_view(original.read_text(encoding='utf-8')), encoding='utf-8')
    path = package / 'root/usr/share/luci/menu.d/luci-mod-status.json'
    menu = json.loads(path.read_text(encoding='utf-8'))
    menu['admin/status/channel_analysis']['action']['path'] = 'status/' + VIEW_NAME.removesuffix('.js')
    path.write_text(json.dumps(menu, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def improve_view(text):
    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise RuntimeError('Channel graph source changed: ' + old[:80])
        text = text.replace(old, new)

    replace("\tcallFrequencyList: rpc.declare({", "\tcallScan: rpc.declare({ object: 'iwinfo', method: 'scan', params: ['device'], expect: { results: [] } }),\n\tcallFrequencyList: rpc.declare({")
    replace('const height = chan_analysis.graph.offsetHeight - 2;', 'const height = chan_analysis.graph.clientHeight;')
    replace('const height_diff = (height-(height-(res.signal*-4)));', "const scale = chan_analysis.scale || { min: -100, max: -20 };\n\t\tconst height_diff = res.local ? 36 : 70 + (scale.max - Math.max(scale.min, Math.min(scale.max, res.signal))) / (scale.max - scale.min) * (height - 70);")
    replace("\t\t})\n\t},\n\n\tresize_channel_graph", "\t\t})\n\t\tif (chan_analysis.axisLabels)\n\t\t\tchan_analysis.graph.firstElementChild.appendChild(chan_analysis.axisLabels);\n\t},\n\n\tresize_channel_graph")
    replace('resize_channel_graph(radio) {', 'resize_channel_graph(radio, force) {')
    replace('(graph.width === width && graph.height === height)', '(!force && graph.width === width && graph.height === height)')
    replace('graph.graph.replaceChildren(graph.template.cloneNode(true));', """graph.graph.replaceChildren(graph.template.cloneNode(true));
        const svg = graph.graph.firstElementChild;
        svg.setAttribute('viewBox', '0 0 ' + graph.graph.clientWidth + ' ' + graph.graph.clientHeight);
        svg.querySelectorAll('line, text').forEach(node => node.remove());
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
            for (const [k,v] of Object.entries({x:8, y:y-5, fill:'#57657a', 'font-size':12})) label.setAttribute(k,v);
            label.textContent = value + ' dBm';
            label.setAttribute('style', 'paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round');
            graph.axisLabels.appendChild(label);
        }""")
    replace('this.resize_channel_graph(radio));', 'this.resize_channel_graph(radio, true));')
    replace("\t\treturn Promise.all([\n\t\t\tradio.dev.getScanList(),\n\t\t\tthis.callInfo(radio.dev.getName())\n\t\t]).then(L.bind(function([results, local_wifi]) {", """\t\treturn radio.dev.getWifiNetworks().then(nets => {
            const iface = nets.find(n => n.isUp() && n.getIfname());
            const device = iface ? iface.getIfname() : radio.dev.getName();
            return Promise.all([this.callScan(device), this.callInfo(device)]);
        }).then(L.bind(function([results, local_wifi]) {""")
    replace('\t\t\tconst rows = [];', """\t\t\tconst rows = [];
            const signals = results.filter(r => r.band == band && Number.isFinite(r.signal) && r.signal >= -110 && r.signal < 0).map(r => r.signal);
            const min = signals.length ? Math.max(-110, Math.floor((Math.min(...signals)-5)/10)*10) : -100;
            const max = signals.length ? Math.min(0, Math.max(min+20, Math.ceil((Math.max(...signals)+5)/10)*10)) : -20;
            chan_analysis.scale = { min, max };
            for (const key of Object.keys(scanCache)) {
                if (scanCache[key].data?.local) { scanCache[key].graph?.group.remove(); delete scanCache[key]; }
            }
            this.resize_channel_graph(radio, true);""")
    replace("if (band + 'g' == radio.dev.get('band')) {", "if (local_wifi.bssid && (local_wifi.frequency >= 5925 ? 6 : local_wifi.frequency >= 4900 ? 5 : 2) == band) {")
    replace("local_wifi.signal = -10;", "local_wifi.signal = -10;\n\t\t\t\t\tlocal_wifi.local = true;")
    replace('this.render_signal_badge(q, local_wifi.signal),', "'—',")
    replace('if (scanCache[k].data.stale)', 'if (!scanCache[k].data.local && scanCache[k].data.stale)')
    replace('if (bands[band].channels.length == 0)', "if (bands[band].channels.length == 0 || (wifiDevs[ifname].dev.get('band') && wifiDevs[ifname].dev.get('band') != band + 'g'))")
    return text
