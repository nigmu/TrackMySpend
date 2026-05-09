"""Stage 1 -> Stage 2: sender keyword filter.

Reads candidate rows from `email_ingest_staging` (stage2_status IS NULL),
matches `from_header` against configured keywords, and writes matched rows
into `email_parse_queue_staging`. Source rows are marked `done` or
`skipped` via stage2_status.
"""

from __future__ import annotations

from datetime import datetime, timezone

from psycopg import Connection

from . import db as pipeline_db
from .keywords import normalized_keywords


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_sender_filter(db: Connection, *, limit: int = 200) -> dict:
    keywords = normalized_keywords(db)
    rows = pipeline_db.fetch_pending_stage1_rows(db, limit=limit)
    matched_at = _now_iso()
    inserted = 0
    skipped = 0

    for row in rows:
        from_header = (row["from_header"] or "").lower()
        matched = next((kw for kw in keywords if kw in from_header), None)
        if not matched:
            pipeline_db.mark_stage1_status(db, row["id"], "skipped")
            skipped += 1
            continue

        rowcount = pipeline_db.insert_parse_queue_row(
            db, stage1=row, matched_keyword=matched, matched_at=matched_at
        )
        pipeline_db.mark_stage1_status(db, row["id"], "done")
        if rowcount > 0:
            inserted += 1

    db.commit()
    return {
        "rows_scanned": len(rows),
        "rows_inserted": inserted,
        "skipped_by_from_header_keywords": skipped,
        "keywords": keywords,
    }
