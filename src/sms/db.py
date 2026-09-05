from __future__ import annotations

import hashlib
from datetime import datetime

from psycopg import Connection

from ..core.logging import get_logger

logger = get_logger(__name__)


def sms_content_hash(
    sender: str | None,
    body: str,
    received_at: datetime | None,
    device_id: str | None,
) -> str:
    """Hash used to dedupe SMS ingest retries.

    device_id is included so the same text from two different phones is
    never merged into one row. received_at is included so a phone that
    resends an old queued message doesn't collide with a new message that
    happens to have identical sender/body text.
    """
    received = received_at.isoformat() if received_at is not None else ""
    payload = "\n".join(
        [
            (sender or "").strip(),
            body,
            received,
            (device_id or "").strip(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def insert_sms(
    conn: Connection,
    sender: str | None,
    body: str,
    received_at: datetime | None,
    device_id: str | None,
) -> tuple[int, bool]:
    digest = sms_content_hash(sender, body, received_at, device_id)
    row = conn.execute(
        """
        INSERT INTO raw_sms_data (sender, body, received_at, device_id, content_hash)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (content_hash) DO NOTHING
        RETURNING id
        """,
        (sender, body, received_at, device_id, digest),
    ).fetchone()
    if row is not None:
        return int(row["id"]), True
    existing = conn.execute(
        "SELECT id FROM raw_sms_data WHERE content_hash = %s",
        (digest,),
    ).fetchone()
    assert existing is not None
    return int(existing["id"]), False


def list_sms(conn: Connection, limit: int = 50, offset: int = 0) -> list[dict]:
    return conn.execute(
        """
        SELECT id, sender, body, received_at, device_id,
               processing_status, error_message, created_at, updated_at
        FROM raw_sms_data
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


def count_sms(conn: Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM raw_sms_data").fetchone()
    return int(row["n"]) if row else 0


def latest_received_at(conn: Connection, device_id: str) -> datetime | None:
    """Max received_at for this device, or None if the device has no rows."""
    row = conn.execute(
        """
        SELECT MAX(received_at) AS latest
        FROM raw_sms_data
        WHERE device_id = %s
        """,
        (device_id.strip(),),
    ).fetchone()
    if row is None or row["latest"] is None:
        return None
    return row["latest"]


if __name__ == "__main__":
    from datetime import UTC, datetime as dt
    from unittest.mock import MagicMock

    when = dt(2026, 9, 2, 20, 0, tzinfo=UTC)
    a = sms_content_hash("VM-HDFCBK", "Rs.100 spent", when, "dev1")
    b = sms_content_hash("VM-HDFCBK", "Rs.100 spent", when, "dev1")
    c = sms_content_hash("VM-HDFCBK", "Rs.100 spent", when, "dev2")
    assert a == b
    assert a != c
    assert len(a) == 64

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"latest": None}
    assert latest_received_at(conn, "dev1") is None
    conn.execute.return_value.fetchone.return_value = {"latest": when}
    assert latest_received_at(conn, "dev1") == when
    print("sms content hash + latest_received_at ok")
