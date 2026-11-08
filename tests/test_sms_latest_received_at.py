"""Unit tests for src.sms.db.latest_received_at (watermark cursor)."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock

from src.core.config import IST
from src.sms.db import latest_received_at

WHEN = datetime(2026, 9, 2, 20, 0, tzinfo=IST)


class TestLatestReceivedAt(unittest.TestCase):
    def test_null_when_no_rows(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"latest": None}
        self.assertIsNone(latest_received_at(conn, "dev1"))

    def test_null_when_fetchone_empty(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        self.assertIsNone(latest_received_at(conn, "dev1"))

    def test_returns_max_timestamp(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"latest": WHEN}
        self.assertEqual(latest_received_at(conn, "dev1"), WHEN)

    def test_strips_device_id(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"latest": None}
        latest_received_at(conn, "  dev1  ")
        conn.execute.assert_called_once()
        self.assertEqual(conn.execute.call_args.args[1], ("dev1",))


if __name__ == "__main__":
    unittest.main()
