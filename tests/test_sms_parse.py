"""Ledger writes and one-row reparse."""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.sms.classify import parse_stored_sms
from src.sms.ledger import LedgerRuleError, create_manual, update


class TestLedgerRules(unittest.TestCase):
    def test_balance_and_debit_require_an_amount(self):
        conn = MagicMock()
        with self.assertRaises(LedgerRuleError) as raised:
            create_manual(conn, {"kind": "balance"})
        self.assertEqual(raised.exception.detail, "amount_paisa is required")
        with self.assertRaises(LedgerRuleError) as raised:
            create_manual(conn, {"kind": "debit"})
        self.assertEqual(raised.exception.detail, "amount_paisa is required")
        conn.execute.assert_not_called()

    def test_manual_balance_stores_blank_text_as_null(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"id": 3}
        create_manual(
            conn,
            {
                "kind": "balance",
                "amount_paisa": 104090,
                "instrument": "  ",
                "counterparty": "cafe",
            },
        )
        insert_sql, params = conn.execute.call_args_list[0].args
        self.assertIn("INSERT INTO transactions_sms", insert_sql)
        self.assertNotIn("raw_sms_id", insert_sql)
        self.assertIn("'manual'", insert_sql)
        self.assertIn("COALESCE(%s, NOW())", insert_sql)
        self.assertEqual(params[0], "balance")
        self.assertEqual(params[1], 104090)
        self.assertIsNone(params[2])
        self.assertEqual(params[4], "cafe")

    def test_null_received_at_is_rejected(self):
        conn = MagicMock()
        with self.assertRaises(LedgerRuleError) as raised:
            create_manual(
                conn,
                {"kind": "debit", "amount_paisa": 100, "sms_received_at": None},
            )
        self.assertEqual(raised.exception.detail, "sms_received_at is required")
        conn.execute.assert_not_called()

    def test_update_sets_updated_at_and_leaves_identity_columns(self):
        conn = MagicMock()
        conn.execute.return_value.rowcount = 1
        conn.execute.return_value.fetchone.return_value = {
            "id": 3,
            "kind": "debit",
            "amount_paisa": 100,
        }
        update(conn, 3, {"counterparty": "cafe", "kind": "balance"})
        sql = conn.execute.call_args_list[1].args[0]
        self.assertIn("counterparty = %s", sql)
        self.assertIn("kind = %s", sql)
        self.assertIn("updated_at = NOW()", sql)
        self.assertNotIn("raw_sms_id", sql)
        self.assertNotIn("template_name", sql)
        self.assertNotIn("created_at", sql)

    def test_patch_to_balance_without_an_amount_is_rejected(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {
            "id": 3,
            "kind": "bill_reminder",
            "amount_paisa": None,
        }
        with self.assertRaises(LedgerRuleError) as raised:
            update(conn, 3, {"kind": "balance"})
        self.assertEqual(raised.exception.detail, "amount_paisa is required")


class TestParseStoredSms(unittest.TestCase):
    def test_missing_raw_sms_does_not_classify(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        self.assertIsNone(parse_stored_sms(conn, 9))
        self.assertEqual(conn.execute.call_count, 1)

    def test_info_leaves_the_ledger_row_and_sets_status(self):
        conn = MagicMock()
        when = datetime(2026, 10, 11, 8, 30, tzinfo=timezone.utc)
        conn.execute.return_value.fetchone.return_value = {
            "body": "Login Alert!",
            "received_at": when,
        }
        result = parse_stored_sms(conn, 4)
        self.assertEqual(result.processing_status, "done")
        self.assertIsNone(result.ledger)
        self.assertEqual(conn.execute.call_count, 2)
        status_sql, status_params = conn.execute.call_args_list[1].args
        self.assertIn("UPDATE raw_sms_data", status_sql)
        self.assertNotIn("DELETE", status_sql)
        self.assertEqual(status_params, ("done", 4))


if __name__ == "__main__":
    unittest.main()
