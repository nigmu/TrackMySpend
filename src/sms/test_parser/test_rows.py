"""Checks that stay local: paisa wording, and one regex row."""

from __future__ import annotations

import json
import unittest

from src.sms.test_parser.rows import FIELDS, jev_mark, noul_question, paisa_as_rupees, regex_row

_UPI = (
    "Sent Rs.1.00\n"
    "From HDFC Bank A/C *3826\n"
    "To NIGAMANANDA  BEHERA\n"
    "On 11/10/26\n"
    "Ref 665001558754\n"
    "Not You?\n"
    "Call 18002586161/SMS BLOCK UPI to 7308080808\n"
)

_BALANCE = (
    "Available Bal in HDFC Bank A/c XX3826 as on yesterday:10-OCT-26 is "
    "INR 763.90. Cheques are subject to clearing.For updated A/C Bal dial 18002703333."
)


class TestRows(unittest.TestCase):
    def test_paisa_is_asked_as_rupees(self):
        self.assertEqual(paisa_as_rupees(100), "1.00")
        self.assertEqual(paisa_as_rupees(6171), "61.71")
        self.assertEqual(paisa_as_rupees(25550), "255.50")
        self.assertEqual(paisa_as_rupees(1), "0.01")
        self.assertEqual(paisa_as_rupees(6267900), "62679.00")
        question = noul_question("amount_paisa", "100")
        self.assertEqual(question["instructions"]["stored_rupees"], "1.00")
        self.assertNotIn("100", json.dumps(question))

    def test_mark(self):
        self.assertEqual(jev_mark(0.5), "TRUE (50.0%)")
        self.assertEqual(jev_mark(0.97), "TRUE (97.0%)")
        self.assertEqual(jev_mark(0.49), "FALSE (51.0%)")

    def test_regex_row(self):
        label, fields = regex_row(_UPI)
        self.assertEqual(label, "upi_debit")
        self.assertEqual(fields["amount_paisa"], "100")
        self.assertEqual(fields["account_mask"], "*3826")
        self.assertEqual(fields["counterparty"], "NIGAMANANDA  BEHERA")
        self.assertEqual(fields["reference"], "665001558754")
        label, fields = regex_row(_BALANCE)
        self.assertEqual(label, "balance_alert")
        self.assertEqual(fields["amount_paisa"], "76390")
        self.assertEqual(fields["account_mask"], "XX3826")
        self.assertEqual(fields["counterparty"], "")
        self.assertEqual(fields["reference"], "")
        absent = noul_question("amount_paisa", "")
        self.assertNotIn("stored_rupees", json.dumps(absent))


if __name__ == "__main__":
    unittest.main()
