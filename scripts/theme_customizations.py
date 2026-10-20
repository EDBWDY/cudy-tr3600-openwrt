"""Apply scoped layout adjustments to the bundled Argon theme."""
from pathlib import Path
import hashlib
import re

RULES = r"""
/* router-layout-adjustments */
/* mounts-card-bottom-padding */
#cbi-fstab-global > .cbi-section-node,
#cbi-fstab > .cbi-section > .cbi-section-create {
 padding-bottom:20px;
}

/* mounts-card-horizontal-padding */
#cbi-fstab > .cbi-section > .cbi-section-table,
#cbi-fstab-global > .cbi-section-node > .table {
 width:calc(100% - 40px) !important;
 margin-left:20px;
 margin-right:20px;
 box-sizing:border-box;
}
#cbi-fstab > .cbi-section > .cbi-section-descr,
#cbi-fstab > .cbi-section > .cbi-section-create {
 padding-left:20px;
 padding-right:20px;
}

/* mounts-native-tbody-responsive */
@media screen and (max-width: 1152px) {
 #cbi-fstab .cbi-section-table > tbody.cbi-section-tbody { display:contents; }
 #cbi-fstab .cbi-section-table-row.placeholder > .td { flex:1 1 100%; width:100% !important; box-sizing:border-box; text-align:center !important; }
 @media (min-width: 769px) {
  #cbi-fstab .cbi-section-table-row:not(.placeholder) > .td { flex:0 0 50%; box-sizing:border-box; min-width:0 !important; width:50% !important; }
 }
}

@media screen and (max-width: 1152px) {
 #cbi-network-interface > .cbi-section-table > tbody { display:block; width:100%; box-sizing:border-box; }
 #cbi-network-interface > .cbi-section-table > tbody > .cbi-section-table-row { width:100%; box-sizing:border-box; }
}
/* interface-card-content-width */
@media screen and (min-width: 769px) and (max-width: 1152px) {
 #cbi-network-interface > .cbi-section-table > tbody > .cbi-section-table-row { justify-content: space-between; }
 #cbi-network-interface > .cbi-section-table > tbody > .cbi-section-table-row > .cbi-value-field {
  flex: 10 10 50%; min-width: 0; box-sizing: border-box;
 }
 #cbi-network-interface > .cbi-section-table > tbody > .cbi-section-table-row > .cbi-section-actions { padding: 13.2px 20px; }
}

body[data-page="admin-status-overview"] p:has(> a[href$="/admin/system/tr3600_usb"]) {
 display:flex; justify-content:flex-end; align-items:center; gap:6px; flex-wrap:wrap;
}
body[data-page="admin-status-overview"] p:has(> a[href$="/admin/system/tr3600_usb"]) > .cbi-button { margin:0; }
/* mounts-table-polish */
@media screen and (min-width:769px) {
 #cbi-fstab-global .cbi-value > .cbi-value-title {
  width:240px;
  white-space:nowrap;
 }
}
#cbi-fstab table {
 border-collapse:separate;
 border-spacing:0;
 border:1px solid rgba(128,128,128,.18);
 border-radius:8px;
 overflow:hidden;
}
#cbi-fstab table .tr > .td,
#cbi-fstab table .tr > .th {
 padding:12px 14px;
 vertical-align:middle;
 border-bottom:1px solid rgba(128,128,128,.12);
}
#cbi-fstab table .tr:last-child > .td { border-bottom:0; }
#cbi-fstab table .tr > .td { background:transparent !important; }
#cbi-fstab table .tr:nth-child(odd),
#cbi-fstab table .tr:nth-child(even) { background:transparent; }
#cbi-fstab table .tr > .th { background:rgba(128,128,128,.055); font-weight:600; }
#cbi-fstab .cbi-section-table-row.placeholder > .td {
 padding:22px 14px;
 opacity:.65;
 font-style:normal;
}
#cbi-fstab .cbi-section-table-row.placeholder em { font-style:normal; }
#cbi-fstab .cbi-section-actions > div {
 display:flex;
 justify-content:flex-end;
 align-items:center;
 gap:8px;
}
#cbi-fstab .cbi-section-actions .cbi-button { margin:0; }
@media screen and (max-width:1152px) {
 #cbi-fstab-global .table .tr:not(.table-titles) {
  align-items:stretch;
  border-bottom:1px solid rgba(128,128,128,.12);
 }
 #cbi-fstab-global .table .tr:last-child { border-bottom:0; }
 #cbi-fstab-global .table .tr > .td {
  height:auto;
  border-top:0;
  border-bottom:0;
 }
 #cbi-fstab .cbi-section-table > .cbi-section-tbody { display:contents; }
 #cbi-fstab .cbi-section-table-row:not(.placeholder) {
  display:grid;
  grid-template-columns:minmax(0,1fr) minmax(0,1fr);
  padding:4px 0 0;
  border:0;
  border-bottom:1px solid rgba(128,128,128,.15);
  box-shadow:none;
 }
 #cbi-fstab .cbi-section-table-row:not(.placeholder):last-child { border-bottom:0; }
 #cbi-fstab .cbi-section-table-row:not(.placeholder) > .td {
  display:flex;
  align-items:center;
  justify-content:flex-start;
  gap:12px;
  width:100% !important;
  min-width:0 !important;
  min-height:44px;
  height:auto;
  box-sizing:border-box;
  text-align:left !important;
  border:0;
  overflow-wrap:anywhere;
 }
 #cbi-fstab .cbi-section-table-row:not(.placeholder) > .td[data-title]::before {
  display:block;
  flex:0 0 64px;
  width:64px;
  padding:0;
  margin:0;
  font-weight:400;
  opacity:.65;
 }
 #cbi-fstab .cbi-section-table-row .cbi-checkbox { justify-content:flex-start; height:20px; }
 #cbi-fstab .cbi-section-table-row > .cbi-section-actions {
  grid-column:1 / -1;
  justify-content:flex-end !important;
  padding:12px 14px;
  margin-top:4px;
  background:rgba(128,128,128,.035) !important;
  border-top:1px solid rgba(128,128,128,.12) !important;
 }
 #cbi-fstab .cbi-section-actions > div { width:100%; }
}
@media screen and (max-width:700px) {
 #cbi-fstab .cbi-section-table-row:not(.placeholder) { grid-template-columns:minmax(0,1fr); }
 #cbi-fstab .cbi-section-table-row:not(.placeholder) > .td[data-title]::before { flex-basis:76px; width:76px; }
}
/* router-scoped-mobile-layout */
@media screen and (max-width:700px) {
 :is(#cbi-fstab-global,#cbi-https-dns-proxy) .cbi-value:not(.hidden):not([hidden]) {
  display:block;
  padding:10px 16px;
  line-height:1.5;
 }
 :is(#cbi-fstab-global,#cbi-https-dns-proxy) .cbi-value > .cbi-value-title {
  display:block;
  float:none;
  width:100%;
  max-width:100%;
  padding:0;
  margin:0 0 8px;
  text-align:left;
  white-space:normal;
  line-height:1.5;
 }
 :is(#cbi-fstab-global,#cbi-https-dns-proxy) .cbi-value > .cbi-value-field {
  display:block;
  width:100%;
  min-width:0;
  max-width:100%;
  clear:both;
 }
 :is(#cbi-fstab-global,#cbi-https-dns-proxy) .cbi-value-description {
  display:block;
  width:100%;
  padding:0;
  margin-top:8px;
  line-height:1.5;
  overflow-wrap:anywhere;
 }
 :is(#cbi-fstab-global,#cbi-https-dns-proxy) .cbi-value-description:empty { display:none; }
 :is(#cbi-fstab-global,#cbi-https-dns-proxy) .cbi-value-field :is(input[type="text"],input[type="number"],select,.cbi-dropdown) {
  width:100% !important;
  min-width:0 !important;
  max-width:100%;
  box-sizing:border-box;
 }
 :is(#cbi-fstab-global,#cbi-https-dns-proxy) .cbi-value-field .cbi-button { max-width:100%; }
 #cbi-fstab-global .cbi-value .cbi-checkbox { justify-content:flex-start; height:24px; }
 #cbi-fstab-global .table .tr:not(.table-titles) {
  display:grid;
  grid-template-columns:minmax(0,1fr);
  padding:6px 0;
 }
 #cbi-fstab-global .table > tbody { display:contents; }
 #cbi-fstab-global .table .tr > .td {
  display:flex;
  align-items:center;
  gap:12px;
  width:100% !important;
  min-width:0;
  padding:8px 12px;
  text-align:left !important;
  box-sizing:border-box;
  overflow-wrap:anywhere;
 }
 #cbi-fstab-global .table .tr > .td::before {
  flex:0 0 76px;
  width:76px;
  font-weight:400;
  text-align:left !important;
  opacity:.65;
 }
 #cbi-fstab .cbi-section-table-row:not(.placeholder) > .td { display:flex !important; padding:10px 12px !important; }
 #cbi-fstab .cbi-section-actions > div { flex-wrap:wrap; }
 #cbi-https-dns-proxy .cbi-section-table {
  display:block;
  width:calc(100% - 32px) !important;
  margin:0 16px;
 }
 #cbi-https-dns-proxy .cbi-section-table > .cbi-section-tbody { display:contents; }
 #cbi-https-dns-proxy .cbi-section-table-row {
  display:grid;
  grid-template-columns:minmax(0,1fr);
  margin-bottom:12px;
  border:1px solid rgba(128,128,128,.18);
  border-radius:8px;
  overflow:hidden;
  box-shadow:none;
 }
 #cbi-https-dns-proxy .cbi-section-table-row[data-title]::before {
  padding:12px;
  text-align:left;
  font-weight:600;
  background:rgba(128,128,128,.055);
  border-bottom:1px solid rgba(128,128,128,.12);
 }
 #cbi-https-dns-proxy .cbi-section-table-row > .cbi-section-table-titles { display:none !important; }
 #cbi-https-dns-proxy .cbi-section-table-row > .td:not(.cbi-section-table-titles) {
  display:flex !important;
  align-items:center;
  gap:12px;
  width:100% !important;
  min-width:0 !important;
  padding:10px 12px !important;
  box-sizing:border-box;
  text-align:left !important;
  border:0;
  overflow-wrap:anywhere;
 }
 #cbi-https-dns-proxy .cbi-section-table-row > .td[data-title]::before {
  flex:0 0 120px;
  width:120px;
  padding:0;
  font-weight:400;
  opacity:.65;
 }
 #cbi-https-dns-proxy .cbi-section-table-row > .cbi-section-actions {
  border-top:1px solid rgba(128,128,128,.12);
  justify-content:flex-end;
 }
 #cbi-https-dns-proxy .cbi-section-actions > div {
  display:flex;
  flex-wrap:wrap;
  align-items:center;
  justify-content:flex-end;
  gap:8px;
 }
 #cbi-https-dns-proxy .cbi-section-actions .cbi-button { margin:0; }
 #cbi-https-dns-proxy .cbi-section-table-row.placeholder > .td { justify-content:center; }
}
"""

def customize_theme(package):
    paths = list(Path(package).rglob('cascade.css'))
    if len(paths) != 1:
        raise RuntimeError('Expected one Argon cascade stylesheet')
    path = paths[0]
    text = path.read_text(encoding='utf-8')
    if '/* router-layout-adjustments */' not in text:
        text = text.rstrip()+'\n'+RULES
    if '/* argon-native-table-compat:' not in text:
        compat = Path(__file__).with_name('argon_table_compat.css').read_text(encoding='utf-8')
        text += '\n'+compat
    if '/* argon-block-field-float-compat */' not in text:
        text += '\n'+Path(__file__).with_name('argon_form_compat.css').read_text(encoding='utf-8')
    if '/* argon-service-control-groups */' not in text:
        text += '\n'+Path(__file__).with_name('argon_service_controls.css').read_text(encoding='utf-8')
    # Withdraw the earlier block-table attempt from prepared build trees too.
    marker='/* argon-legacy-table-mobile-compat */'
    if marker in text:
        start=text.index(marker)
        pos=start+len(marker)
        for _ in range(2):
            pos=text.index('{',pos)+1
            depth=1
            while depth:
                if text[pos]=='{': depth+=1
                elif text[pos]=='}': depth-=1
                pos+=1
        text=text[:start]+text[pos:]
    if '/* argon-scroll-table-compat */' not in text:
        text += '\n'+Path(__file__).with_name('argon_legacy_tables.css').read_text(encoding='utf-8')
    path.write_text(text, encoding='utf-8')
    css_version = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    # LuCI derives every module's cache key from luci.js's version query.
    for header in [*Path(package).rglob('header.ut'), *Path(package).rglob('header.htm')]:
        data=header.read_text(encoding='utf-8')
        data = re.sub(r'(css/cascade\.css\?v=)([^"\s]+)',
                      lambda match: match[1] + match[2].split('-')[0] + '-router-css-' + css_version,
                      data)
        header.write_text(data, encoding='utf-8')
        if 'luci.js?v=' in data and '-service-controls-1' not in data:
            data,n=re.subn(r'(luci\.js\?v=)([^\"]+)(\")',r'\1\2-service-controls-1\3',data)
            if n != 1:
                raise RuntimeError('Unexpected LuCI script version markup')
            header.write_text(data,encoding='utf-8')
        data=header.read_text(encoding='utf-8')
        if 'luci.js?v=' in data and '-ts-scroll-2' not in data:
            data,n=re.subn(r'(luci\.js\?v=)([^\"]+)(\")',r'\1\2-ts-scroll-2\3',data)
            if n!=1: raise RuntimeError('Unexpected LuCI script version markup')
            header.write_text(data,encoding='utf-8')
