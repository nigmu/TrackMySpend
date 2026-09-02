"""Unit tests for src.mail.service.match_sender (sender_filters matching)."""

import unittest

from src.mail.service import match_sender


class TestMatchSender(unittest.TestCase):
    def test_matches_substring_case_insensitively(self):
        self.assertEqual(match_sender("alerts@HDFCBK.bank.in", ["hdfcbk"]), "hdfcbk")

    def test_returns_first_matching_pattern(self):
        result = match_sender("no-reply@icicibank.com", ["hdfcbk", "icicibank"])
        self.assertEqual(result, "icicibank")

    def test_no_match_returns_none(self):
        self.assertIsNone(match_sender("someone@example.com", ["hdfcbk"]))

    def test_none_sender_returns_none(self):
        self.assertIsNone(match_sender(None, ["hdfcbk"]))

    def test_empty_patterns_returns_none(self):
        self.assertIsNone(match_sender("alerts@hdfcbk.bank.in", []))


if __name__ == "__main__":
    unittest.main()
