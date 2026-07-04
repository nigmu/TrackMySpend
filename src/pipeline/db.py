"""SQL helpers for all non-auth tables.

Owns:
- email_raw_ingest (stage 1)
- email_parse_queue (stage 2)
- transactions
- filter_keywords

Each helper takes a `Connection` parameter; commits and rollbacks belong to
service-layer orchestration, not to these helpers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable

from psycopg import Connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _email_sent_at(message: dict) -> datetime | None:
    iso = message.get("date_header_iso")
    if iso:
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    dh = message.get("date_header")
    if dh:
        try:
            dt = parsedate_to_datetime(dh)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError, OSError):
            pass
    return None


def _gmail_received_at(message: dict) -> datetime | None:
    g = message.get("gmail_received_at_utc")
    if not g:
        return None
    try:
        return datetime.fromisoformat(str(g).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _internal_epoch_ms(message: dict) -> int | None:
    raw = message.get("internal_date_ms")
    if raw is None or raw == "":
        return None
    try:
        return int(str(raw))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Stage 0 -> Stage 1: email_raw_ingest
# ---------------------------------------------------------------------------

def _ingest_message_values(message: dict) -> tuple:
    return (
        message.get("account_id"),
        message.get("gmail_message_id"),
        message.get("thread_id"),
        message.get("from"),
        message.get("subject"),
        _email_sent_at(message),
        _gmail_received_at(message),
        _internal_epoch_ms(message),
        message.get("snippet"),
        json.dumps(message, ensure_ascii=True, sort_keys=True),
    )


def truncate_ingest_staging(db: Connection) -> None:
    db.execute("DELETE FROM email_raw_ingest")


def insert_ingest_staging_messages(
    db: Connection,
    messages: Iterable[dict],
    fetched_at: str | None = None,
) -> int:
    """Idempotent insert into stage 1; returns number of rows actually inserted.

    `fetched_at` is accepted for API compatibility; ingest timestamps are DB defaults.
    """
    _ = fetched_at or _now_iso()
    inserted = 0
    for message in messages:
        result = db.execute(
            """
            INSERT INTO email_raw_ingest (
                email_account_id, gmail_message_id, gmail_thread_id,
                sender_header, subject, email_sent_at, gmail_received_at,
                gmail_internal_epoch_ms, snippet, raw_payload_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (gmail_message_id) DO NOTHING
            """,
            _ingest_message_values(message),
        )
        if result.rowcount and result.rowcount > 0:
            inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Stage 1 -> Stage 2: email_parse_queue (sender filter)
# ---------------------------------------------------------------------------

def fetch_pending_stage1_rows(db: Connection, *, limit: int) -> list[dict]:
    rows = db.execute(
        """
        SELECT
            id,
            email_account_id,
            sender_header,
            subject,
            email_sent_at,
            gmail_received_at,
            gmail_internal_epoch_ms,
            snippet,
            raw_payload_json
        FROM email_raw_ingest
        WHERE etl_status = 'PENDING'
        ORDER BY id ASC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return list(rows)


def mark_stage1_status(db: Connection, row_id: int, status: str) -> None:
    db.execute(
        "UPDATE email_raw_ingest SET etl_status = %s WHERE id = %s",
        (status, row_id),
    )


def insert_parse_queue_row(
    db: Connection,
    *,
    stage1: dict,
    matched_keyword: str,
) -> int:
    """Insert a row into email_parse_queue; returns rowcount (0 or 1)."""
    result = db.execute(
        """
        INSERT INTO email_parse_queue (
            raw_ingest_id, email_account_id, sender_header, subject,
            email_sent_at, gmail_received_at, gmail_internal_epoch_ms,
            snippet, matched_pattern
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (raw_ingest_id) DO NOTHING
        """,
        (
            stage1["id"],
            stage1["email_account_id"],
            stage1["sender_header"],
            stage1["subject"],
            stage1["email_sent_at"],
            stage1["gmail_received_at"],
            stage1["gmail_internal_epoch_ms"],
            stage1["snippet"],
            matched_keyword,
        ),
    )
    return result.rowcount or 0


# ---------------------------------------------------------------------------
# Stage 2 -> Transactions
# ---------------------------------------------------------------------------

def fetch_pending_stage2_rows(db: Connection) -> list[dict]:
    rows = db.execute(
        """
        SELECT
            pq.id,
            pq.snippet,
            pq.email_sent_at,
            ri.raw_payload_json
        FROM email_parse_queue pq
        JOIN email_raw_ingest ri ON ri.id = pq.raw_ingest_id
        WHERE pq.etl_status = 'PENDING'
        ORDER BY pq.id ASC
        """
    ).fetchall()
    return list(rows)


def parse_queue_etl_counts(db: Connection) -> dict[str, int]:
    """Counts by etl_status for observability (endpoint responses, debugging)."""
    row = db.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE etl_status = 'PENDING') AS pending,
            COUNT(*) FILTER (WHERE etl_status = 'PARSED') AS parsed,
            COUNT(*) AS total
        FROM email_parse_queue
        """
    ).fetchone()
    assert row is not None
    return {
        "pending": int(row["pending"]),
        "parsed": int(row["parsed"]),
        "total": int(row["total"]),
    }


def count_transactions(db: Connection) -> int:
    row = db.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()
    assert row is not None
    return int(row["n"])


def list_transactions(db: Connection, *, limit: int = 50, offset: int = 0) -> list[dict]:
    rows = db.execute(
        """
        SELECT
            id, parse_queue_id, transaction_type, amount, transaction_ts,
            bank, instrument, channel, account_last4,
            counterparty, counterparty_vpa, reference_number, extras,
            etl_insert_ts
        FROM transactions
        ORDER BY COALESCE(transaction_ts, etl_insert_ts) DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()
    return [dict(row) for row in rows]


def update_parse_status(db: Connection, row_id: int, status: str = "PARSED") -> None:
    db.execute(
        "UPDATE email_parse_queue SET etl_status = %s WHERE id = %s",
        (status, row_id),
    )


def insert_transaction(
    db: Connection,
    *,
    parse_queue_id: int,
    transaction_type: str,
    amount: int,
    transaction_ts: Any | None = None,
    bank: str | None = None,
    instrument: str | None = None,
    channel: str | None = None,
    account_last4: str | None = None,
    counterparty: str | None = None,
    counterparty_vpa: str | None = None,
    reference_number: str | None = None,
    extras: dict | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO transactions (
            parse_queue_id, transaction_type, amount, transaction_ts,
            bank, instrument, channel, account_last4,
            counterparty, counterparty_vpa, reference_number, extras
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            parse_queue_id, transaction_type, amount, transaction_ts,
            bank, instrument, channel, account_last4,
            counterparty, counterparty_vpa, reference_number,
            json.dumps(extras) if extras else None,
        ),
    )


# ---------------------------------------------------------------------------
# filter_keywords
# ---------------------------------------------------------------------------

def list_sender_keywords(db: Connection) -> list[str]:
    rows = db.execute(
        "SELECT keyword FROM filter_keywords ORDER BY id ASC"
    ).fetchall()
    return [row["keyword"] for row in rows]


def insert_sender_keyword(db: Connection, keyword: str) -> bool:
    """Insert a keyword; returns True if a new row was inserted."""
    result = db.execute(
        """
        INSERT INTO filter_keywords (keyword)
        VALUES (%s)
        ON CONFLICT (keyword) DO NOTHING
        """,
        (keyword,),
    )
    return bool(result.rowcount and result.rowcount > 0)
