import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from promote_final_release import IMAGE, validate, release_metadata


class FinalReleaseValidationTests(unittest.TestCase):
    def test_draft_upload_is_checked_by_release_id_instead_of_tag_endpoint(self):
        endpoint = 'https://api.github.com/repos/owner/repo/releases/123'
        with patch.dict('os.environ', {'GH_REPO': 'owner/repo'}), patch(
                'promote_final_release.gh', side_effect=[
                    json.dumps({'apiUrl': endpoint}),
                    json.dumps({'tag_name': '2026.10.20', 'draft': True, 'assets': []})]) as command:
            self.assertTrue(release_metadata('2026.10.20')['draft'])
            command.assert_called_with('api', endpoint, capture=True)

    def fixture(self, root):
        source = 'a' * 40
        checkpoint = {'source_commit': source, 'stage': 'firmware', 'stage_complete': True}
        (root / IMAGE).write_bytes(b'verified image')
        (root / 'same-build-packages.tar.gz').write_bytes(b'matching packages')
        (root / 'sha256sums').write_text('firmware checksum manifest')
        (root / 'UNVERIFIED.json').write_text('{}')
        hashes = ''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n'
                         for path in sorted(root.iterdir()))
        (root / 'artifact-sha256sums').write_text(hashes)
        (root / 'validation-status.json').write_text(json.dumps({'image': 'success', 'source_tests': 'success'}))
        (root / 'privacy-verification.json').write_text(json.dumps({
            'source': {'source_files_checked': 1}, 'image': {
                'shadow_has_no_password_hashes': True, 'configuration_files_checked': 1}}))
        (root / 'verification.json').write_text(json.dumps({'board': 'cudy,tr3600-v1',
            'image_sha256': hashlib.sha256((root / IMAGE).read_bytes()).hexdigest()}))
        return source, checkpoint

    def test_accepts_only_complete_matching_validated_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source, checkpoint = self.fixture(root)
            self.assertEqual(validate(root, checkpoint, source)['board'], 'cudy,tr3600-v1')

    def test_refuses_incomplete_or_wrong_compiler_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source, checkpoint = self.fixture(root)
            for change in [{'stage_complete': False}, {'stage': 'rust'}, {'source_commit': 'b' * 40}]:
                with self.subTest(change=change), self.assertRaises(RuntimeError):
                    validate(root, dict(checkpoint, **change), source)

    def test_refuses_failed_image_or_source_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source, checkpoint = self.fixture(root)
            for field in ['image', 'source_tests']:
                status = {'image': 'success', 'source_tests': 'success'}
                status[field] = 'failure'
                (root / 'validation-status.json').write_text(json.dumps(status))
                with self.subTest(field=field), self.assertRaises(RuntimeError):
                    validate(root, checkpoint, source)

    def test_refuses_private_image_or_changed_image(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source, checkpoint = self.fixture(root)
            privacy = root / 'privacy-verification.json'
            original = privacy.read_bytes()
            privacy.write_text('{}')
            with self.assertRaises(RuntimeError):
                validate(root, checkpoint, source)
            privacy.write_bytes(original)
            (root / IMAGE).write_bytes(b'replaced after verification')
            with self.assertRaises(RuntimeError):
                validate(root, checkpoint, source)

    def test_refuses_changed_packages_and_unsafe_manifest_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source, checkpoint = self.fixture(root)
            (root / 'same-build-packages.tar.gz').write_bytes(b'changed')
            with self.assertRaises(RuntimeError):
                validate(root, checkpoint, source)
            (root / 'artifact-sha256sums').write_text('0' * 64 + '  ../outside\n')
            with self.assertRaises(RuntimeError):
                validate(root, checkpoint, source)


if __name__ == '__main__':
    unittest.main()
