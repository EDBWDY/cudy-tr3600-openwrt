"""Use the owner's Samba label in the page title and navigation menu."""
import json
import re


def relabel_script(text):
    changed, count = re.subn(r"_\(\s*(['\"])Network Shares\1\s*\)", "'Samba'", text)
    if count != 1:
        raise RuntimeError('Expected one pinned Samba page title')
    changed = changed.replace("'use strict';", "'use strict';\n'require ui';", 1)
    changed, count = re.subn(r'render\s*:\s*function\(stats\)\s*\{',
                            'render: function(stats) { ui.menu.flushCache();', changed)
    if count != 1:
        raise RuntimeError('Expected one pinned Samba render function')
    return changed


def customize_package(package):
    script = package / 'htdocs/luci-static/resources/view/samba4.js'
    alternate = script.with_name('samba4-tr3600-v2.js')
    alternate.write_text(relabel_script(script.read_text(encoding='utf-8')), encoding='utf-8')
    path = package / 'root/usr/share/luci/menu.d/luci-app-samba4.json'
    menu = json.loads(path.read_text(encoding='utf-8'))
    item = menu['admin/services/samba4']
    item['title'] = 'Samba'
    item['action']['path'] = 'samba4-tr3600-v2'
    path.write_text(json.dumps(menu, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
