import unittest
from unittest.mock import patch

from src.sms.classify import classify_sms


class TestUnmatchedReason(unittest.TestCase):
    def test_unknown_body_is_no_template(self):
        result = classify_sms("hello from the bank")
        self.assertEqual(result.processing_status, "unmatched")
        self.assertIsNone(result.category_id)
        self.assertEqual(result.reason, "no_template")
        self.assertIsNone(result.template)

    @patch("src.sms.classify.parse_amount_paisa", return_value=None)
    def test_amount_miss_keeps_the_template(self, _parse):
        body = (
            "Spent Rs.255.5 On HDFC Bank Card 6517 At UBER INDIA SYSTEMS PRI "
            "On 2026-10-07:20:54:25"
        )
        result = classify_sms(body)
        self.assertEqual(result.processing_status, "unmatched")
        self.assertIsNone(result.category_id)
        self.assertIsNone(result.ledger)
        self.assertEqual(result.reason, "amount_unparsed")
        self.assertEqual(result.template, "credit_card_spend")


if __name__ == "__main__":
    unittest.main()
