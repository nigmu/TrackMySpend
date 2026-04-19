import re
from datetime import datetime, timezone
from pathlib import Path

from .. import global_configs
from ..db_connection import connect


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized_keywords() -> list[str]:
    return [k.strip().lower() for k in global_configs.PARSER_FROM_HEADER_KEYWORDS if k and k.strip()]


def get_sender_keywords() -> list[str]:
    return list(global_configs.PARSER_FROM_HEADER_KEYWORDS)


def _persist_sender_keywords_to_global_configs(keywords: list[str]) -> None:
    config_path = Path(__file__).resolve().parents[1] / "global_configs.py"
    content = config_path.read_text(encoding="utf-8")
    replacement = "PARSER_FROM_HEADER_KEYWORDS = [\n" + "".join(
        f'    "{kw}",\n' for kw in keywords
    ) + "]"
    updated = re.sub(
        r"PARSER_FROM_HEADER_KEYWORDS\s*=\s*\[(?:.|\n)*?\]",
        replacement,
        content,
        count=1,
    )
    if updated == content:
        raise ValueError("Could not persist keywords to global_configs.py.")
    config_path.write_text(updated, encoding="utf-8")


def add_sender_keyword(keyword: str) -> list[str]:
    candidate = keyword.strip()
    if not candidate:
        raise ValueError("Keyword cannot be empty.")
    lowered = candidate.lower()
    existing = {k.lower() for k in global_configs.PARSER_FROM_HEADER_KEYWORDS}
    if lowered not in existing:
        global_configs.PARSER_FROM_HEADER_KEYWORDS.append(candidate)
        _persist_sender_keywords_to_global_configs(global_configs.PARSER_FROM_HEADER_KEYWORDS)
    return list(global_configs.PARSER_FROM_HEADER_KEYWORDS)


def stage_sender_regex_matches(limit: int = 200) -> dict:
    conn = connect()
    try:
        sender_keywords = _normalized_keywords()
        rows = conn.execute(
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

        matched_at = _now_iso()
        inserted = 0
        skipped_by_sender_keywords = 0
        for row in rows:
            from_header = (row["from_header"] or "").lower()
            matched_keyword = next((kw for kw in sender_keywords if kw in from_header), None)
            if not matched_keyword:
                skipped_by_sender_keywords += 1
                conn.execute(
                    """
                    UPDATE email_ingest_staging
                    SET stage2_status = 'skipped'
                    WHERE id = %s
                    """,
                    (row["id"],),
                )
                continue

            result = conn.execute(
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
                    row["id"],
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
                    matched_keyword,
                    row["fetched_at"],
                    matched_at,
                    row["raw_json"],
                ),
            )
            conn.execute(
                """
                UPDATE email_ingest_staging
                SET stage2_status = 'done'
                WHERE id = %s
                """,
                (row["id"],),
            )
            if result.rowcount and result.rowcount > 0:
                inserted += 1

        conn.commit()
        return {
            "rows_scanned": len(rows),
            "rows_inserted": inserted,
            "skipped_by_from_header_keywords": skipped_by_sender_keywords,
            "keywords": sender_keywords,
        }
    finally:
        conn.close()
