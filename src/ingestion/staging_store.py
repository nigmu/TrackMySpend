import json
from datetime import datetime, timezone

from psycopg import Connection

from ..db_connection import connect


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
        fetched_at,
        json.dumps(message, ensure_ascii=True, sort_keys=True),
    )


def _insert_parser_staging_with_conn(conn: Connection, messages: list[dict], fetched_at: str) -> int:
    inserted = 0
    for message in messages:
        result = conn.execute(
            """
            INSERT INTO email_ingest_staging (
                email_account_id, email_address, gmail_message_id, thread_id,
                from_header, to_header, subject, date_header, internal_date_ms,
                gmail_received_at_utc, date_header_iso, snippet, fetched_at, raw_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email_account_id, gmail_message_id) DO NOTHING
            """,
            _message_values(message, fetched_at),
        )
        if result.rowcount and result.rowcount > 0:
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
    conn = connect()
    try:
        if not keep_existing:
            conn.execute("DELETE FROM email_ingest_staging")
        inserted = _insert_parser_staging_with_conn(conn, messages, fetched_at)
        conn.commit()
        return inserted
    finally:
        conn.close()
