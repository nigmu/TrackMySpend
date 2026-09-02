"""Unit tests for src.sms.db.sms_content_hash (SMS ingest dedupe key)."""

import unittest
from datetime import UTC, datetime

from src.sms.db import sms_content_hash

WHEN = datetime(2026, 9, 2, 20, 0, tzinfo=UTC)


class TestSmsContentHash(unittest.TestCase):
    def test_identical_inputs_produce_identical_hash(self):
        a = sms_content_hash("VM-HDFCBK", "Rs.100 spent", WHEN, "dev1")
        b = sms_content_hash("VM-HDFCBK", "Rs.100 spent", WHEN, "dev1")
        self.assertEqual(a, b)

    def test_different_device_id_changes_hash(self):
        a = sms_content_hash("VM-HDFCBK", "Rs.100 spent", WHEN, "dev1")
        b = sms_content_hash("VM-HDFCBK", "Rs.100 spent", WHEN, "dev2")
        self.assertNotEqual(a, b)

    def test_different_received_at_changes_hash(self):
        a = sms_content_hash("VM-HDFCBK", "Rs.100 spent", WHEN, "dev1")
        b = sms_content_hash("VM-HDFCBK", "Rs.100 spent", None, "dev1")
        self.assertNotEqual(a, b)

    def test_different_body_changes_hash(self):
        a = sms_content_hash("VM-HDFCBK", "Rs.100 spent", WHEN, "dev1")
        b = sms_content_hash("VM-HDFCBK", "Rs.200 spent", WHEN, "dev1")
        self.assertNotEqual(a, b)

    def test_missing_sender_and_device_id_still_hashable(self):
        digest = sms_content_hash(None, "Rs.100 spent", WHEN, None)
        self.assertEqual(len(digest), 64)

    def test_returns_hex_sha256(self):
        digest = sms_content_hash("VM-HDFCBK", "Rs.100 spent", WHEN, "dev1")
        self.assertEqual(len(digest), 64)
        int(digest, 16)  # raises ValueError if not valid hex


if __name__ == "__main__":
    unittest.main()
