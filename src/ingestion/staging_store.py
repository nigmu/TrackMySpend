import json
import sqlite3
from datetime import datetime, timezone

from ..global_configs import DB_PATH

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _message_values(message: dict, fetched_at: str) -> tuple:
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
        message.get("full_message_text"),
        fetched_at,
        json.dumps(message, ensure_ascii=True, sort_keys=True),
    )


def _insert_parser_staging_with_conn(conn: sqlite3.Connection, messages: list[dict], fetched_at: str) -> int:
    inserted = 0
    for message in messages:
        result = conn.execute(
            """
            INSERT OR IGNORE INTO ingestion_parser_staging (
                email_account_id, email_address, gmail_message_id, thread_id,
                from_header, to_header, subject, date_header, internal_date_ms,
                gmail_received_at_utc, date_header_iso, snippet, full_body, fetched_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _message_values(message, fetched_at),
        )
        if result.rowcount > 0:
            inserted += 1
    return inserted


def store_for_parser(messages: list[dict], keep_existing: bool = True) -> int:
    """
    Store messages in the parser staging table.
    change keep_existing to False to delete all existing messages in the table before storing new ones.
    """
    if not messages:
        return 0
    fetched_at = _now_iso()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        if not keep_existing:
            conn.execute("DELETE FROM ingestion_parser_staging")
        inserted = _insert_parser_staging_with_conn(conn, messages, fetched_at)
        conn.commit()
        return inserted
    finally:
        conn.close()

