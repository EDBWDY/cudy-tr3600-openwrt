import unittest
from refresh_target import allowed_delta, REVIEWED_THEME_REFRESH


class TargetRefreshBoundaryTests(unittest.TestCase):
    def test_only_the_reviewed_theme_digest_pair_is_accepted(self):
        name = 'scripts/theme_customizations.py'
        old, new = REVIEWED_THEME_REFRESH
        self.assertEqual(allowed_delta({name: old}, {name: new}), [name])
        for before, after in [('unreviewed', new), (old, 'unreviewed')]:
            with self.subTest(before=before, after=after), self.assertRaises(RuntimeError):
                allowed_delta({name: before}, {name: after})

    def test_kernel_and_controller_fixes_preserve_compiler_identity(self):
        old = {'sources.json': 'same', 'scripts/prepare.py': 'same',
               'experiments/turboacc/mt7987-wed-kernel.patch': 'old'}
        new = dict(old, **{'experiments/turboacc/mt7987-wed-kernel.patch': 'fixed',
                          'package/example/files/controller': 'new'})
        self.assertEqual(len(allowed_delta(old, new)), 2)

    def test_source_pin_or_host_compiler_preparation_change_is_never_accepted(self):
        for name in ['sources.json', 'scripts/prepare.py', 'scripts/environment.sh',
                     'experiments/turboacc/sources.json']:
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                allowed_delta({name: 'old'}, {name: 'different'})
