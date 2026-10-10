import hashlib
import unittest
from unittest.mock import patch
import kernel_audit as audit


class KernelMetadataComparisonTests(unittest.TestCase):
    def fixture(self):
        data = bytearray(audit.KERNEL_SIZE)
        for p in audit.HOST_OFFSETS:
            data[p:p + 13] = b'runnervm00000'
        data[audit.BUILD_ID_OFFSET:audit.BUILD_ID_OFFSET + 16] = audit.BUILD_ID_HEADER
        return data

    def test_builder_name_and_derived_build_id_are_the_only_permitted_changes(self):
        data = self.fixture()
        expected = hashlib.sha256(data).hexdigest()
        for p in audit.HOST_OFFSETS:
            data[p:p + 13] = b'runnervmabc12'
        data[audit.BUILD_ID_OFFSET + 16:audit.BUILD_ID_OFFSET + 36] = bytes(range(20))
        with patch.object(audit, 'EXPECTED_NORMALIZED_SHA256', expected):
            self.assertEqual(audit.verify_kernel_bytes(data), expected)

    def test_changed_code_byte_is_rejected(self):
        data = self.fixture()
        expected = hashlib.sha256(data).hexdigest()
        data[4096] ^= 1
        with patch.object(audit, 'EXPECTED_NORMALIZED_SHA256', expected):
            with self.assertRaises(RuntimeError):
                audit.verify_kernel_bytes(data)

    def test_other_gnu_notes_are_not_ignored(self):
        data = self.fixture()
        expected = hashlib.sha256(data).hexdigest()
        data[9593552 + 16] ^= 1
        with patch.object(audit, 'EXPECTED_NORMALIZED_SHA256', expected):
            with self.assertRaises(RuntimeError):
                audit.verify_kernel_bytes(data)

    def test_changed_known_note_structure_is_rejected(self):
        data = self.fixture()
        data[audit.BUILD_ID_OFFSET] ^= 1
        with self.assertRaises(RuntimeError):
            audit.verify_kernel_bytes(data)
