import unittest
from refresh_target import allowed_delta


class TargetRefreshBoundaryTests(unittest.TestCase):
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
