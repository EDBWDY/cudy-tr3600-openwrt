import unittest
from mount_labels import relabel_script, BUTTON_LABEL, DESCRIPTION
from checkpoint import recipe
from refresh_customizations import validate_refresh
from pathlib import Path

class MountLabelTests(unittest.TestCase):
    def test_only_the_two_visible_labels_change(self):
        original = "fs.exec('/sbin/block',['mount']); o=button(_('Mount attached devices'),_('Attempt to enable configured mount points for attached devices'));"
        result = relabel_script(original)
        self.assertIn("fs.exec('/sbin/block',['mount']);", result)
        self.assertIn(BUTTON_LABEL, result)
        self.assertIn(DESCRIPTION, result)
        self.assertEqual(result, "fs.exec('/sbin/block',['mount']); o=button(\"" + BUTTON_LABEL + '\",\"' + DESCRIPTION + '\");')

    def test_changed_upstream_text_fails_instead_of_silently_missing_the_patch(self):
        with self.assertRaises(RuntimeError):
            relabel_script('upstream changed')

    def test_matching_mount_recipe_can_resume(self):
        root = Path(__file__).resolve().parents[1]
        metadata = {'workspace': str(root.resolve()), 'recipe': recipe(root)}
        validate_refresh(metadata, root, recipe(root))

if __name__ == '__main__':
    unittest.main()
