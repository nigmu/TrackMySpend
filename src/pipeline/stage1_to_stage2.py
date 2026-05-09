"""Stage 1 -> Stage 2: sender keyword filter.

Reads candidate rows from `email_raw_ingest` (etl_status = 'PENDING'),
matches `sender_header` against configured keywords, and writes matched rows
into `email_parse_queue`. Source rows are marked DONE or SKIPPED via etl_status.
"""

from __future__ import annotations

from psycopg import Connection

from . import db as pipeline_db
from .keywords import normalized_keywords


def run_sender_filter(db: Connection, *, limit: int = 200) -> dict:
    keywords = normalized_keywords(db)
    rows = pipeline_db.fetch_pending_stage1_rows(db, limit=limit)
    inserted = 0
    skipped = 0

    for row in rows:
        sender = (row["sender_header"] or "").lower()
        matched = next((kw for kw in keywords if kw in sender), None)
        if not matched:
            pipeline_db.mark_stage1_status(db, row["id"], "SKIPPED")
            skipped += 1
            continue

        rowcount = pipeline_db.insert_parse_queue_row(
            db, stage1=row, matched_keyword=matched
        )
        pipeline_db.mark_stage1_status(db, row["id"], "DONE")
        if rowcount > 0:
            inserted += 1

    db.commit()
    return {
        "rows_scanned": len(rows),
        "rows_inserted": inserted,
        "skipped_by_from_header_keywords": skipped,
        "keywords": keywords,
    }
