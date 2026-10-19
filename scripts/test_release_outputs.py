"""A validation rerun must never replace preserved firmware deliverables."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import release_outputs


class ReportUploadTest(unittest.TestCase):
    def test_reports_cannot_clobber_compiler_outputs_or_original_hash_list(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ['firmware.bin', 'same-build-packages.tar.gz',
                         'artifact-sha256sums', 'verification.json',
                         'privacy-verification.json', 'validation-status.json',
                         'image-validation.log']:
                (root / name).write_text('fixture', encoding='utf-8')
            with patch.object(release_outputs, 'ROOT', root), \
                    patch.object(release_outputs, 'gh') as gh:
                release_outputs.publish('candidate', '.', reports=True)
            uploaded = {call.args[3].name for call in gh.call_args_list}
            self.assertEqual(uploaded, {'verification.json',
                                       'privacy-verification.json',
                                       'validation-status.json',
                                       'image-validation.log'})


if __name__ == '__main__':
    unittest.main()
