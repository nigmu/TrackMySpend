from __future__ import annotations

import hashlib
from datetime import datetime

from psycopg import Connection

from ..core.logging import get_logger
from .ledger import LEDGER_FROM

logger = get_logger(__name__)


def sms_content_hash(
    sender: str | None,
    body: str,
    device_id: str | None,
) -> str:
    """Hash used to dedupe SMS ingest retries / live-vs-inbox reuploads.

    device_id is included so the same text from two different phones is
    never merged into one row. received_at is intentionally excluded:
    Android PDU time and inbox DATE can differ by ~1s for the same SMS.
    Financial SMS bodies already carry unique refs (UPI ids, etc.).
    """
    payload = "\n".join(
        [
            (sender or "").strip(),
            body,
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
    digest = sms_content_hash(sender, body, device_id)
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


def rehash_sms_content_hashes(conn: Connection) -> int:
    """Rewrite content_hash to sender+body+device_id; drop duplicate rows.

    Returns the number of duplicate rows deleted. Safe to run on every migrate.
    """
    from collections import defaultdict

    conn.execute("DROP INDEX IF EXISTS idx_raw_sms_data_content_hash")
    rows = conn.execute(
        "SELECT id, sender, body, device_id FROM raw_sms_data"
    ).fetchall()
    by_hash: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        digest = sms_content_hash(row["sender"], row["body"], row["device_id"])
        by_hash[digest].append(int(row["id"]))

    deleted = 0
    for digest, ids in by_hash.items():
        ids.sort()
        keep, drop = ids[0], ids[1:]
        if drop:
            conn.execute("DELETE FROM raw_sms_data WHERE id = ANY(%s)", (drop,))
            deleted += len(drop)
        conn.execute(
            """
            UPDATE raw_sms_data
            SET content_hash = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (digest, keep),
        )

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_sms_data_content_hash
            ON raw_sms_data (content_hash)
        """
    )
    return deleted


def list_sms(conn: Connection, limit: int = 50, offset: int = 0) -> list[dict]:
    return conn.execute(
        """
        SELECT id, sender, body, received_at, device_id,
               processing_status, error_message, created_at, updated_at
        FROM raw_sms_data
        ORDER BY received_at DESC NULLS LAST, id DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


def count_sms(conn: Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM raw_sms_data").fetchone()
    return int(row["n"]) if row else 0


def set_processing_status(conn: Connection, raw_sms_id: int, processing_status: str) -> None:
    conn.execute(
        """
        UPDATE raw_sms_data
        SET processing_status = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (processing_status, raw_sms_id),
    )


def list_sms_transactions(conn: Connection, limit: int = 50, offset: int = 0) -> list[dict]:
    return conn.execute(
        LEDGER_FROM
        + " ORDER BY t.sms_received_at DESC NULLS LAST, t.id DESC LIMIT %s OFFSET %s",
        (limit, offset),
    ).fetchall()


def count_sms_transactions(conn: Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM transactions_sms").fetchone()
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
    from datetime import datetime as dt, timedelta, timezone
    from unittest.mock import MagicMock

    when = dt(2026, 9, 2, 20, 0, tzinfo=timezone(timedelta(hours=5, minutes=30), name="IST"))
    a = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev1")
    b = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev1")
    c = sms_content_hash("VM-HDFCBK", "Rs.100 spent", "dev2")
    assert a == b
    assert a != c
    assert len(a) == 64

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"latest": None}
    assert latest_received_at(conn, "dev1") is None
    conn.execute.return_value.fetchone.return_value = {"latest": when}
    assert latest_received_at(conn, "dev1") == when
    print("sms content hash + latest_received_at ok")
