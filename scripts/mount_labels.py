"""Clarify the mount action label while preserving the upstream mount behavior."""
import json
import re

VIEW_NAME = 'mounts-tr3600-v1.js'
BUTTON_LABEL = '挂载已配置的分区'
DESCRIPTION = '按已保存且启用的挂载配置挂载分区'

def relabel_script(text):
    for original, replacement in [
        ('Mount attached devices', BUTTON_LABEL),
        ('Attempt to enable configured mount points for attached devices', DESCRIPTION),
    ]:
        pattern = r"_\(\s*(['\"])" + re.escape(original) + r"\1\s*\)"
        text, count = re.subn(pattern, json.dumps(replacement, ensure_ascii=False), text)
        if count != 1:
            raise RuntimeError('Expected exactly one upstream mount label: ' + original)
    return text

def customize_package(package):
    original = package / 'htdocs/luci-static/resources/view/system/mounts.js'
    original.with_name(VIEW_NAME).write_text(relabel_script(original.read_text(encoding='utf-8')), encoding='utf-8')
    path = package / 'root/usr/share/luci/menu.d/luci-mod-system.json'
    menu = json.loads(path.read_text(encoding='utf-8'))
    menu['admin/system/mounts']['action']['path'] = 'system/' + VIEW_NAME.removesuffix('.js')
    path.write_text(json.dumps(menu, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
