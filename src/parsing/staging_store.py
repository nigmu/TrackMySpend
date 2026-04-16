import sqlite3
import re
from datetime import datetime, timezone
from typing import Pattern

from ..global_configs import DB_PATH

SENDER_REGEX_PATTERNS = [
    r"(?i)alerts?",
    r"(?i)no-?reply",
    r"(?i)bank",
    r"(?i)statement",
]
COMPILED_SENDER_REGEX: list[Pattern[str]] = [re.compile(p) for p in SENDER_REGEX_PATTERNS]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stage_sender_regex_matches(limit: int = 200) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        rows = conn.execute(
            """
            SELECT
                email_account_id, email_address, gmail_message_id, thread_id,
                from_header, to_header, subject, date_header, internal_date_ms,
                gmail_received_at_utc, date_header_iso, snippet, fetched_at, raw_json
            FROM ingestion_parser_staging
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        matched_at = _now_iso()
        inserted = 0
        for row in rows:
            from_header = row["from_header"] or ""
            for pattern in COMPILED_SENDER_REGEX:
                if not pattern.search(from_header):
                    continue
                result = conn.execute(
                    """
                    INSERT OR IGNORE INTO parsing_sender_regex_staging (
                        email_account_id, email_address, gmail_message_id, thread_id,
                        from_header, to_header, subject, date_header, internal_date_ms,
                        gmail_received_at_utc, date_header_iso, snippet, matched_pattern,
                        fetched_at, matched_at, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["email_account_id"],
                        row["email_address"],
                        row["gmail_message_id"],
                        row["thread_id"],
                        row["from_header"],
                        row["to_header"],
                        row["subject"],
                        row["date_header"],
                        row["internal_date_ms"],
                        row["gmail_received_at_utc"],
                        row["date_header_iso"],
                        row["snippet"],
                        pattern.pattern,
                        row["fetched_at"],
                        matched_at,
                        row["raw_json"],
                    ),
                )
                if result.rowcount > 0:
                    inserted += 1

        conn.commit()
        return {
            "rows_scanned": len(rows),
            "rows_inserted": inserted,
            "patterns": SENDER_REGEX_PATTERNS,
        }
    finally:
        conn.close()
