"""Build-input regressions for responsive controls and native table layouts."""
import tempfile
import hashlib
import unittest
from pathlib import Path

from service_controls import customize_source as customize_controls
from tailscale_tables import customize_source as customize_tables, customize_sources
from theme_customizations import customize_theme

CONTROLS = '''var buttonsText = E("output", { id: pkg.Name + "-buttons" }, [
    btn_start, btn_gap, btn_action, btn_gap, btn_stop, btn_gap_long,
    btn_enable, btn_gap, btn_disable,
]);'''
TABLES = '''function renderStatus() {
    return E([
        statusTable,
        E('div', { 'style': 'margin-top: 25px;' }, [
            E('h4', {}, _('Network Devices')),
            peersContent,
        ]),
    ]);
}
function update(view, content) { view.replaceChildren(content); }
'''


class ResponsiveCustomizationTests(unittest.TestCase):
    def test_controls_accept_formatted_feed_and_compressed_package_source(self):
        for source in [CONTROLS, CONTROLS.replace('\n', '').replace('    ', '')]:
            with self.subTest(source=source):
                result = customize_controls(source)
                self.assertEqual(result.count('cbi-service-control-group'), 2)
                self.assertNotIn('btn_gap', result)
                self.assertEqual(customize_controls(result), result)

    def test_controls_reject_changed_upstream_structure(self):
        with self.assertRaises(RuntimeError):
            customize_controls(CONTROLS.replace('btn_disable,', 'new_control,'))

    def test_tables_retain_table_nodes_and_poll_update_in_both_source_formats(self):
        for source in [TABLES, TABLES.replace('\n', '').replace('    ', '')]:
            with self.subTest(source=source):
                result = customize_tables(source)
                self.assertEqual(result.count('cbi-table-scroll'), 2)
                self.assertIn('view.replaceChildren(content)', result)
                self.assertEqual(customize_tables(result), result)

    def test_tables_reject_unrecognized_return_structure(self):
        with self.assertRaises(RuntimeError):
            customize_tables(TABLES.replace('statusTable,', 'unknownTable,'))

    def test_source_discovery_changes_only_the_community_view(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'feeds/example/htdocs/luci-static/resources/view/tailscale.js'
            target.parent.mkdir(parents=True)
            target.write_text('/* service_status_display */\n' + TABLES, encoding='utf-8')
            unrelated = root / 'feeds/example/tailscale.js'
            unrelated.write_text('unrelated source', encoding='utf-8')
            customize_sources(root)
            self.assertIn('cbi-table-scroll', target.read_text(encoding='utf-8'))
            self.assertEqual(unrelated.read_text(encoding='utf-8'), 'unrelated source')

    def test_theme_migrates_withdrawn_rules_without_losing_other_styles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            css = root / 'cascade.css'
            header = root / 'header.ut'
            css.write_text('/* router-layout-adjustments */\n.keep {color:red}\n'
                '/* argon-legacy-table-mobile-compat */\n'
                '@media(max-width:768px){.old{display:block}}\n'
                '@media(max-width:600px){.old td{display:table-cell}}\n'
                '.keep-after {color:blue}\n', encoding='utf-8')
            header.write_text('<link href="{{ media }}/css/cascade.css?v=2.4.6">'
                '<script src="{{ resource }}/luci.js?v={{ version.luciversion }}"></script>', encoding='utf-8')
            customize_theme(root)
            result, result_header = css.read_bytes(), header.read_bytes()
            customize_theme(root)
            self.assertEqual(css.read_bytes(), result)
            self.assertEqual(header.read_bytes(), result_header)
            self.assertIn(b'.keep {color:red}', result)
            self.assertIn(b'.keep-after {color:blue}', result)
            self.assertNotIn(b'argon-legacy-table-mobile-compat', result)
            self.assertEqual(result.count(b'argon-scroll-table-compat'), 1)
            self.assertIn(b'-ts-scroll-2', result_header)
            self.assertIn(('2.4.6-router-css-' + hashlib.sha256(result).hexdigest()[:12]).encode(), result_header)
            css.write_text(css.read_text() + '\n.new-rule {color:green}\n')
            customize_theme(root)
            self.assertNotEqual(header.read_bytes(), result_header)


if __name__ == '__main__':
    unittest.main()
