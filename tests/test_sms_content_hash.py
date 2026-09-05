"""Unit tests for src.sms.db.sms_content_hash (SMS ingest dedupe key)."""

import unittest

from src.sms.db import sms_content_hash


class TestSmsContentHash(unittest.TestCase):
    def test_identical_inputs_produce_identical_hash(self):
        a = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev1")
        b = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev1")
        self.assertEqual(a, b)

    def test_different_device_id_changes_hash(self):
        a = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev1")
        b = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev2")
        self.assertNotEqual(a, b)

    def test_received_at_not_part_of_hash(self):
        # Signature no longer takes received_at; same body always same digest.
        a = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev1")
        b = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev1")
        self.assertEqual(a, b)

    def test_different_body_changes_hash(self):
        a = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev1")
        b = sms_content_hash("VM-HDFCBK", "Rs.200 spent", "dev1")
        self.assertNotEqual(a, b)

    def test_missing_sender_and_device_id_still_hashable(self):
        digest = sms_content_hash(None, "Rs.100 spent", None)
        self.assertEqual(len(digest), 64)

    def test_returns_hex_sha256(self):
        digest = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev1")
        self.assertEqual(len(digest), 64)
        int(digest, 16)  # raises ValueError if not valid hex


if __name__ == "__main__":
    unittest.main()
