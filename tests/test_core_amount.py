"""Unit tests for src.core.amount (source-agnostic rupee-amount parser)."""

import unittest

from src.core.amount import parse_amount_paisa


class TestParseAmountPaisa(unittest.TestCase):
    def test_rs_with_decimal_and_thousands_separator(self):
        self.assertEqual(parse_amount_paisa("Rs. 1,234.56 debited"), 123456)

    def test_inr_prefix(self):
        self.assertEqual(parse_amount_paisa("INR 500 credited"), 50000)

    def test_rs_without_dot(self):
        self.assertEqual(parse_amount_paisa("Rs 100 spent"), 10000)

    def test_case_insensitive(self):
        self.assertEqual(parse_amount_paisa("rs. 42 debited"), 4200)

    def test_no_amount_returns_none(self):
        self.assertIsNone(parse_amount_paisa("hello there"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_amount_paisa(""))

    def test_uses_first_match_when_multiple_amounts_present(self):
        self.assertEqual(parse_amount_paisa("Rs.100 then Rs.200"), 10000)


if __name__ == "__main__":
    unittest.main()
