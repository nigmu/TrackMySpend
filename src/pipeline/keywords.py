"""Sender-keyword CRUD service.

Keywords drive the stage-1 -> stage-2 sender filter. They live in the
`parser_sender_keywords` table; if the table is empty we fall back to the
seed list in `core.config.DEFAULT_PARSER_FROM_HEADER_KEYWORDS`.
"""

from __future__ import annotations

from psycopg import Connection

from ..core.config import DEFAULT_PARSER_FROM_HEADER_KEYWORDS
from . import db as pipeline_db


def get_sender_keywords(db: Connection) -> list[str]:
    keywords = pipeline_db.list_sender_keywords(db)
    if keywords:
        return keywords
    return list(DEFAULT_PARSER_FROM_HEADER_KEYWORDS)


def add_sender_keyword(db: Connection, keyword: str) -> list[str]:
    candidate = (keyword or "").strip()
    if not candidate:
        raise ValueError("Keyword cannot be empty.")
    pipeline_db.insert_sender_keyword(db, candidate)
    db.commit()
    return get_sender_keywords(db)


def normalized_keywords(db: Connection) -> list[str]:
    return [k.strip().lower() for k in get_sender_keywords(db) if k and k.strip()]
