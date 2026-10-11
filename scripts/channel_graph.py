"""Size channel graphs only while visible, and redraw them after tab/size changes."""
import json

VIEW_NAME = 'channel_analysis-tr3600-v1.js'


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
    return text


def customize_package(package):
    original = package / 'htdocs/luci-static/resources/view/status/channel_analysis.js'
    original.with_name(VIEW_NAME).write_text(customize_view(original.read_text(encoding='utf-8')), encoding='utf-8')
    path = package / 'root/usr/share/luci/menu.d/luci-mod-status.json'
    menu = json.loads(path.read_text(encoding='utf-8'))
    menu['admin/status/channel_analysis']['action']['path'] = 'status/' + VIEW_NAME.removesuffix('.js')
    path.write_text(json.dumps(menu, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
