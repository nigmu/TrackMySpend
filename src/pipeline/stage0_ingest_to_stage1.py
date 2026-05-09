"""Stage 0 -> Stage 1: write Gmail message dicts into `email_raw_ingest`."""

from __future__ import annotations

from psycopg import Connection

from . import db as pipeline_db


def store_messages_in_stage1(
    db: Connection,
    messages: list[dict],
    *,
    keep_existing: bool = True,
) -> int:
    """Insert messages into stage 1.

    Set `keep_existing=False` to clear the staging table first.
    Returns the number of rows actually inserted (post-dedupe).
    """
    if not messages:
        return 0
    if not keep_existing:
        pipeline_db.truncate_ingest_staging(db)
    inserted = pipeline_db.insert_ingest_staging_messages(db, messages)
    db.commit()
    return inserted
