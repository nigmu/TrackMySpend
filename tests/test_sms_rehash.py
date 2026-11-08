"""Unit tests for rehash_sms_content_hashes (duplicate collapse)."""

import unittest
from unittest.mock import MagicMock, call

from src.sms.db import rehash_sms_content_hashes, sms_content_hash


class TestRehashSmsContentHashes(unittest.TestCase):
    def test_deletes_duplicate_keeps_lowest_id(self):
        body = "Sent Rs.10 Ref 123"
        digest = sms_content_hash("AD-HDFCBK", body, "dev1")
        conn = MagicMock()
        # First execute: DROP INDEX; second: SELECT; then DELETE / UPDATE / CREATE INDEX
        select_result = MagicMock()
        select_result.fetchall.return_value = [
            {"id": 99, "sender": "AD-HDFCBK", "body": body, "device_id": "dev1"},
            {"id": 100, "sender": "AD-HDFCBK", "body": body, "device_id": "dev1"},
        ]

        def execute_side_effect(sql, params=None):
            if "SELECT id, sender" in sql:
                return select_result
            return MagicMock()

        conn.execute.side_effect = execute_side_effect
        deleted = rehash_sms_content_hashes(conn)
        self.assertEqual(deleted, 1)
        # DELETE should target id 100
        delete_calls = [
            c for c in conn.execute.call_args_list
            if isinstance(c.args[0], str) and "DELETE FROM raw_sms_data" in c.args[0]
        ]
        self.assertEqual(len(delete_calls), 1)
        self.assertEqual(delete_calls[0].args[1], ([100],))
        update_calls = [
            c for c in conn.execute.call_args_list
            if isinstance(c.args[0], str) and "UPDATE raw_sms_data" in c.args[0]
        ]
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0].args[1], (digest, 99))


if __name__ == "__main__":
    unittest.main()
