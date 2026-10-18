"""Keep channel labels outside the plotting rectangle and follow theme colors."""
def external_axes(s):
    s=s.replace("'style': 'width:100%;height:400px;border:1px solid #000;background:#fff'", "'style': 'width:100%;height:400px;border:1px solid #999;overflow:visible'")
    s=s.replace("[E('br'),csvg,E('br'),table,E('br')]", "[E('div', {style:'padding:18px 16px 52px 76px;overflow:visible'}, csvg),table,E('br')]")
    s=s.replace("svg.querySelectorAll('line, text').forEach(node => node.remove());", """svg.style.overflow = 'visible';
        svg.querySelectorAll('line, text').forEach(node => node.remove());
        const clip = document.createElementNS('http://www.w3.org/2000/svg', 'clipPath');
        graph.clipId = 'channel-clip-' + radio.band + '-' + radio.dev.getName();
        clip.id = graph.clipId;
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', graph.graph.clientWidth); rect.setAttribute('height', graph.graph.clientHeight);
        clip.appendChild(rect); svg.appendChild(clip);""")
    s=s.replace("group.appendChild(line);", "group.setAttribute('clip-path', 'url(#' + chan_analysis.clipId + ')');\n\t\t\tgroup.appendChild(line);")
    s=s.replace("{x:8, y:y-5, fill:'#57657a', 'font-size':12}", "{x:-10, y:y+4, fill:'currentColor', 'font-size':12, 'text-anchor':'end'}")
    s=s.replace("label.textContent = value + ' dBm';", "label.textContent = Number(value.toFixed(1));")
    s=s.replace("label.setAttribute('style', 'paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round');", "label.setAttribute('style', 'fill:currentColor;font-family:inherit');")
    s=s.replace("this.create_channel_graph(graph, radio.channels, radio.band);", """this.create_channel_graph(graph, radio.channels, radio.band);
        const axisTitle = (text, x, y, rotate) => {
            const el = document.createElementNS('http://www.w3.org/2000/svg','text');
            el.textContent=text; el.setAttribute('x',x); el.setAttribute('y',y);
            el.setAttribute('style','fill:currentColor;font-size:13px;font-family:inherit;text-anchor:middle');
            if (rotate) el.setAttribute('transform','rotate(-90 '+x+' '+y+')');
            graph.axisLabels.appendChild(el);
        };
        axisTitle('信号强度 (dBm)', -58, graph.graph.clientHeight/2, true);
        axisTitle('Wi-Fi 信道', graph.graph.clientWidth/2, graph.graph.clientHeight+40);
        this.update_graph_theme(radio);""")
    s=s.replace("elem.setAttribute('y', 15);", "elem.setAttribute('y', chan_graph.clientHeight + 20);")
    s=s.replace("'fill:#eee; font-size:9pt; font-family:sans-serif; text-shadow:1px 1px 1px #000'", "'fill:currentColor;font-size:12px;font-family:inherit;text-anchor:middle'")
    s=s.replace("elem.setAttribute('x', pos + 5);", "elem.setAttribute('x', pos);")
    s=s.replace("\t\t\tgraph.appendChild(elem);\n\t\t}\n\n\t\tchan_analysis.col_width", "\t\t\tchan_analysis.axisLabels.appendChild(elem);\n\t\t}\n\n\t\tchan_analysis.col_width")
    s=s.replace("if (channel < 100)\n\t\t\t\t\tcreateGraphText(G,curr_offset-(step/2), channel);\n\t\t\t\telse\n\t\t\t\t\tcreateGraphText(G,curr_offset-step, channel);", "if (i % Math.max(1, Math.ceil(34 / (step*4))) === 0) createGraphText(G,curr_offset+step, channel);")
    s=s.replace("createGraphText(G,curr_offset+step, channel);\n\t\t\t}", "if (i % Math.max(1, Math.ceil(24 / step)) === 0) createGraphText(G,curr_offset+step, channel);\n\t\t\t}")
    s=s.replace("'stroke:black;stroke-width:'", "'stroke:currentColor;opacity:0.25;stroke-width:'")
    s=s.replace("\tbind_channel_graph(radio) {", """
    update_graph_theme(radio) {
        let node = radio.graph.graph.parentElement, dark = false;
        while (node) {
            const rgb = getComputedStyle(node).backgroundColor.match(/[\\d.]+/g);
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
\tbind_channel_graph(radio) {
        const recolor = () => requestAnimationFrame(() => this.update_graph_theme(radio));
        const themeObserver = new MutationObserver(recolor);
        themeObserver.observe(document.documentElement, {attributes:true, attributeFilter:['class','style']});
        themeObserver.observe(document.body, {attributes:true, attributeFilter:['class','style']});
        matchMedia('(prefers-color-scheme: dark)').addEventListener('change', recolor);""")
    # Old wide-channel overlay must stay inside its own network group.
    s=s.replace("chan_analysis.graph.firstElementChild.lastElementChild.appendChild(main);", "")
    s=s.replace("if (i % Math.max(1, Math.ceil(34 / (step*4))) === 0) if (i % Math.max(1, Math.ceil(24 / step)) === 0)", "if (i % Math.max(1, Math.ceil(34 / (step*4))) === 0)")
    return s
