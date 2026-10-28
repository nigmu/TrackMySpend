"""Unit tests for parsing one SMS and for manual ledger writes."""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from src.sms.classify import (
    SmsClassification,
    SmsLedger,
    apply_sms_classification,
    parse_new_sms,
    parse_stored_sms,
)
from src.sms.db import insert_manual_ledger, update_sms_transaction
from src.sms.routes import ManualLedgerWrite, _require_amount, _write_fields


class TestParseNewSms(unittest.TestCase):
    @patch("src.sms.classify.classify_sms", return_value=SmsClassification("upi_debit", "done", None))
    @patch("src.sms.classify.apply_sms_classification")
    def test_classifies_without_deleting(self, apply, classify):
        conn = MagicMock()
        result = parse_new_sms(conn, 7, "body")
        classify.assert_called_once_with("body")
        apply.assert_called_once_with(conn, 7, result)
        conn.execute.assert_not_called()


class TestApplySmsClassification(unittest.TestCase):
    def test_upsert_keeps_created_at_and_replaces_parser_fields(self):
        conn = MagicMock()
        when = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)
        conn.execute.return_value.fetchone.return_value = {"received_at": when}
        ledger = SmsLedger("debit", 25000, "upi", "1234", "Cafe", "ref1", "upi_debit")
        apply_sms_classification(conn, 5, SmsClassification("upi_debit", "done", ledger))
        insert_sql, params = conn.execute.call_args_list[1].args
        self.assertIn("ON CONFLICT (raw_sms_id) DO UPDATE", insert_sql)
        self.assertIn("updated_at = NOW()", insert_sql)
        self.assertNotIn("created_at", insert_sql.split("DO UPDATE", 1)[1])
        self.assertEqual(params[7], when)
        self.assertEqual(params[8], "upi_debit")
        status_sql = conn.execute.call_args_list[2].args[0]
        self.assertIn("UPDATE raw_sms_data", status_sql)

    def test_no_ledger_deletes_sms_ledger_row(self):
        conn = MagicMock()
        apply_sms_classification(conn, 5, SmsClassification("otp", "ignored", None))
        delete_sql, params = conn.execute.call_args_list[0].args
        self.assertIn("DELETE FROM transactions_sms WHERE raw_sms_id", delete_sql)
        self.assertEqual(params, (5,))
        self.assertIn("UPDATE raw_sms_data", conn.execute.call_args_list[1].args[0])


class TestParseStoredSms(unittest.TestCase):
    def test_missing_raw_sms_does_not_classify(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        with patch("src.sms.classify.classify_sms") as classify:
            self.assertIsNone(parse_stored_sms(conn, 9))
        classify.assert_not_called()


class TestManualLedgerWrites(unittest.TestCase):
    def test_insert_stays_out_of_raw_sms(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"id": 3}
        insert_manual_ledger(
            conn,
            kind="debit",
            amount_paisa=100,
            instrument=None,
            account_mask=None,
            counterparty="cafe",
            reference=None,
            sms_received_at=None,
        )
        insert_sql = conn.execute.call_args_list[0].args[0]
        self.assertIn("INSERT INTO transactions_sms", insert_sql)
        self.assertNotIn("raw_sms_data", insert_sql)
        self.assertIn("'manual'", insert_sql)
        self.assertIn("COALESCE(%s, NOW())", insert_sql)

    def test_update_sets_updated_at_and_leaves_identity_columns(self):
        conn = MagicMock()
        conn.execute.return_value.rowcount = 1
        conn.execute.return_value.fetchone.return_value = {"id": 3}
        update_sms_transaction(conn, 3, {"counterparty": "cafe"})
        sql = conn.execute.call_args_list[0].args[0]
        self.assertIn("counterparty = %s", sql)
        self.assertIn("updated_at = NOW()", sql)
        self.assertNotIn("raw_sms_id", sql)
        self.assertNotIn("template_name", sql)
        self.assertNotIn("created_at", sql)

    def test_blank_text_is_null_and_null_received_at_is_rejected(self):
        fields = _write_fields(ManualLedgerWrite(instrument="  "))
        self.assertIsNone(fields["instrument"])
        with self.assertRaises(HTTPException) as raised:
            _write_fields(ManualLedgerWrite(sms_received_at=None))
        self.assertEqual(raised.exception.status_code, 400)
        with self.assertRaises(HTTPException):
            _require_amount("debit", None)


if __name__ == "__main__":
    unittest.main()
