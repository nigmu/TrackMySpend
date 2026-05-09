"""SQL helpers for all non-auth tables.

Owns:
- email_ingest_staging (stage 1)
- email_parse_queue_staging (stage 2)
- transactions
- parser_sender_keywords

Each helper takes a `Connection` parameter; commits and rollbacks belong to
service-layer orchestration, not to these helpers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

from psycopg import Connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Stage 0 -> Stage 1: email_ingest_staging
# ---------------------------------------------------------------------------

def _ingest_message_values(message: dict, fetched_at: str) -> tuple:
    return (
        message.get("account_id"),
        message.get("email_address"),
        message.get("gmail_message_id"),
        message.get("thread_id"),
        message.get("from"),
        message.get("to"),
        message.get("subject"),
        message.get("date_header"),
        message.get("internal_date_ms"),
        message.get("gmail_received_at_utc"),
        message.get("date_header_iso"),
        message.get("snippet"),
        fetched_at,
        json.dumps(message, ensure_ascii=True, sort_keys=True),
    )


def truncate_ingest_staging(db: Connection) -> None:
    db.execute("DELETE FROM email_ingest_staging")


def insert_ingest_staging_messages(
    db: Connection,
    messages: Iterable[dict],
    fetched_at: str | None = None,
) -> int:
    """Idempotent insert into stage 1; returns number of rows actually inserted."""
    fetched_at = fetched_at or _now_iso()
    inserted = 0
    for message in messages:
        result = db.execute(
            """
            INSERT INTO email_ingest_staging (
                email_account_id, email_address, gmail_message_id, thread_id,
                from_header, to_header, subject, date_header, internal_date_ms,
                gmail_received_at_utc, date_header_iso, snippet, fetched_at, raw_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email_account_id, gmail_message_id) DO NOTHING
            """,
            _ingest_message_values(message, fetched_at),
        )
        if result.rowcount and result.rowcount > 0:
            inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Stage 1 -> Stage 2: email_parse_queue_staging (sender filter)
# ---------------------------------------------------------------------------

def fetch_pending_stage1_rows(db: Connection, *, limit: int) -> list[dict]:
    rows = db.execute(
        """
        SELECT
            id,
            email_account_id, email_address, gmail_message_id, thread_id,
            from_header, to_header, subject, date_header, internal_date_ms,
            gmail_received_at_utc, date_header_iso, snippet, fetched_at, raw_json
        FROM email_ingest_staging
        WHERE stage2_status IS NULL
        ORDER BY id ASC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return list(rows)


def mark_stage1_status(db: Connection, row_id: int, status: str) -> None:
    db.execute(
        "UPDATE email_ingest_staging SET stage2_status = %s WHERE id = %s",
        (status, row_id),
    )


def insert_parse_queue_row(
    db: Connection,
    *,
    stage1: dict,
    matched_keyword: str,
    matched_at: str,
) -> int:
    """Insert a row into email_parse_queue_staging; returns rowcount (0 or 1)."""
    result = db.execute(
        """
        INSERT INTO email_parse_queue_staging (
            stg1_id, email_account_id, email_address, gmail_message_id, thread_id,
            from_header, to_header, subject, date_header, internal_date_ms,
            gmail_received_at_utc, date_header_iso, snippet, matched_pattern,
            fetched_at, matched_at, raw_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (email_account_id, gmail_message_id) DO NOTHING
        """,
        (
            stage1["id"],
            stage1["email_account_id"],
            stage1["email_address"],
            stage1["gmail_message_id"],
            stage1["thread_id"],
            stage1["from_header"],
            stage1["to_header"],
            stage1["subject"],
            stage1["date_header"],
            stage1["internal_date_ms"],
            stage1["gmail_received_at_utc"],
            stage1["date_header_iso"],
            stage1["snippet"],
            matched_keyword,
            stage1["fetched_at"],
            matched_at,
            stage1["raw_json"],
        ),
    )
    return result.rowcount or 0


# ---------------------------------------------------------------------------
# Stage 2 -> Transactions
# ---------------------------------------------------------------------------

def fetch_pending_stage2_rows(db: Connection) -> list[dict]:
    rows = db.execute(
        """
        SELECT id, snippet, date_header
        FROM email_parse_queue_staging
        WHERE parse_status IS NULL
        ORDER BY id ASC
        """
    ).fetchall()
    return list(rows)


def update_parse_status(db: Connection, row_id: int, status: str = "PARSED") -> None:
    db.execute(
        "UPDATE email_parse_queue_staging SET parse_status = %s WHERE id = %s",
        (status, row_id),
    )


def insert_transaction(
    db: Connection,
    *,
    stg2_id: int,
    transaction_type: str,
    amount: int,
    transaction_date: Any | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO transactions (stg2_id, transaction_type, amount, transaction_date)
        VALUES (%s, %s, %s, %s)
        """,
        (stg2_id, transaction_type, amount, transaction_date),
    )


# ---------------------------------------------------------------------------
# parser_sender_keywords
# ---------------------------------------------------------------------------

def list_sender_keywords(db: Connection) -> list[str]:
    rows = db.execute(
        "SELECT keyword FROM parser_sender_keywords ORDER BY id ASC"
    ).fetchall()
    return [row["keyword"] for row in rows]


def insert_sender_keyword(db: Connection, keyword: str) -> bool:
    """Insert a keyword; returns True if a new row was inserted."""
    result = db.execute(
        """
        INSERT INTO parser_sender_keywords (keyword)
        VALUES (%s)
        ON CONFLICT (keyword) DO NOTHING
        """,
        (keyword,),
    )
    return bool(result.rowcount and result.rowcount > 0)
