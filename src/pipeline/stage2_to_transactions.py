"""Stage 2 -> Transactions: parse snippets and insert into `transactions`.

One run = one DB transaction. On any failure we rollback the whole run so
no partial `etl_status = 'PARSED'` updates are persisted.
"""

from __future__ import annotations

from psycopg import Connection

from ..parsing import parse_text
from . import db as pipeline_db


def run_staging_to_transactions(db: Connection) -> dict:
    rows = pipeline_db.fetch_pending_stage2_rows(db)
    inserted = 0
    errors: list[str] = []

    for row in rows:
        row_id = row["id"]
        try:
            parsed = parse_text(row["snippet"])
            transaction_type = parsed["type"]
            transaction_amount = int(parsed["amount"])
            transaction_ts = row["email_sent_at"]
            pipeline_db.insert_transaction(
                db,
                parse_queue_id=row_id,
                transaction_type=transaction_type,
                amount=transaction_amount,
                transaction_ts=transaction_ts,
            )
            pipeline_db.update_parse_status(db, row_id, "PARSED")
            inserted += 1
        except Exception as e:
            errors.append(f"stg id {row_id}: {e!s}")
            db.rollback()
            return {
                "staging_rows_seen": len(rows),
                "transactions_inserted": 0,
                "errors": errors,
                "rolled_back": True,
            }

    db.commit()
    return {
        "staging_rows_seen": len(rows),
        "transactions_inserted": inserted,
        "errors": errors,
        "rolled_back": False,
    }
