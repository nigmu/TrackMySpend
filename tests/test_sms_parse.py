"""Unit tests for parse_new_sms and reparse_all_sms."""

import unittest
from unittest.mock import MagicMock, patch

from src.sms.classify import SmsClassification, parse_new_sms, reparse_all_sms


class TestParseNewSms(unittest.TestCase):
    @patch("src.sms.classify.classify_sms", return_value=SmsClassification("upi_debit", "done", None))
    @patch("src.sms.classify.apply_sms_classification")
    def test_classifies_without_deleting(self, apply, classify):
        conn = MagicMock()
        result = parse_new_sms(conn, 7, "body")
        classify.assert_called_once_with("body")
        apply.assert_called_once_with(conn, 7, result)
        conn.execute.assert_not_called()


class TestReparseAllSms(unittest.TestCase):
    @patch("src.sms.classify.classify_sms")
    @patch("src.sms.classify.apply_sms_classification")
    def test_deletes_ledger_then_applies_every_row(self, apply, classify):
        classify.side_effect = [
            SmsClassification("card_otp", "ignored", None),
            SmsClassification(None, "unmatched", None),
        ]
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            {"id": 1, "body": "otp"},
            {"id": 2, "body": "unknown"},
        ]
        counts = reparse_all_sms(conn)
        self.assertEqual(counts, {"total": 2, "done": 0, "ignored": 1, "unmatched": 1})
        sqls = [call.args[0] for call in conn.execute.call_args_list]
        self.assertIn("FROM raw_sms_data", sqls[0])
        self.assertIn("DELETE FROM transactions_sms", sqls[1])
        self.assertEqual(conn.execute.call_args_list[1].args[1], (1,))
        self.assertIn("DELETE FROM transactions_sms", sqls[2])
        self.assertEqual(conn.execute.call_args_list[2].args[1], (2,))
        self.assertEqual(apply.call_count, 2)


if __name__ == "__main__":
    unittest.main()
