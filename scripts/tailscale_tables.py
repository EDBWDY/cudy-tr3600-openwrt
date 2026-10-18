"""Preserve native Tailscale tables inside generic scrolling containers."""
from pathlib import Path
import re

def customize_source(text):
    if 'cbi-table-scroll' in text:
        return text
    # Feeds contain formatted source; installed packages may be minified.
    result, status_count = re.subn(
        r'(return\s+E\(\s*\[\s*)statusTable(?=\s*,)',
        r"\1E('div',{'class':'cbi-table-scroll'},statusTable)", text)
    result, peers_count = re.subn(
        r'\bpeersContent(?=\s*,?\s*\]\s*\)\s*,?\s*\]\s*\)\s*;)',
        "E('div',{'class':'cbi-table-scroll'},peersContent)", result)
    if status_count != 1 or peers_count != 1:
        raise RuntimeError('Unexpected Tailscale table renderer; inspect before changing')
    return result

def customize_package(package):
    paths=list(Path(package).rglob('view/tailscale.js'))
    if len(paths)!=1:
        raise RuntimeError('Expected one community Tailscale view')
    path=paths[0]
    path.write_text(customize_source(path.read_text(encoding='utf-8')),encoding='utf-8')

def customize_sources(source_root):
    seen=set()
    for folder in ['feeds','package/custom']:
        for path in (Path(source_root)/folder).rglob('tailscale.js'):
            if path.parent.name!='view' or path.resolve() in seen:
                continue
            seen.add(path.resolve())
            text=path.read_text(encoding='utf-8')
            if 'service_status_display' in text and 'Network Devices' in text:
                path.write_text(customize_source(text),encoding='utf-8')
