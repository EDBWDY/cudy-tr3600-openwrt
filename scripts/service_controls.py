"""Replace fixed whitespace in DoH service controls with semantic groups."""
from pathlib import Path
import re

def customize_source(text):
    if 'cbi-service-control-group' in text:
        return text
    pattern = r'var buttonsText\s*=\s*E\(["\']output["\'],\s*\{\s*id\s*:\s*pkg\.Name\s*\+\s*["\']-buttons["\']\s*\},\s*\[\s*btn_start\s*,\s*btn_gap\s*,\s*btn_action\s*,\s*btn_gap\s*,\s*btn_stop\s*,\s*btn_gap_long\s*,\s*btn_enable\s*,\s*btn_gap\s*,\s*btn_disable\s*,?\s*\]\s*\);'
    replacement = 'var buttonsText=E("output",{id:pkg.Name+"-buttons",class:"cbi-service-controls"},[E("span",{class:"cbi-service-control-group"},[btn_start,btn_action,btn_stop]),E("span",{class:"cbi-service-control-group"},[btn_enable,btn_disable])]);'
    result,count = re.subn(pattern,replacement,text)
    if count != 1:
        raise RuntimeError('Unexpected DoH service control markup; inspect before changing')
    return result

def customize_package(package):
    paths=list(Path(package).rglob('https-dns-proxy/status.js'))
    if len(paths) != 1:
        raise RuntimeError('Expected one DoH status renderer')
    path=paths[0]
    path.write_text(customize_source(path.read_text(encoding='utf-8')),encoding='utf-8')
