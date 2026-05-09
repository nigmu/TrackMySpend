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

    def _response(*, rolled_back: bool) -> dict:
        pq = pipeline_db.parse_queue_etl_counts(db)
        tx_n = pipeline_db.count_transactions(db)
        tx_inserted = 0 if rolled_back else inserted
        out = {
            # Rows picked up from email_parse_queue with etl_status = PENDING (this run only).
            "staging_rows_seen": len(rows),
            "transactions_inserted": tx_inserted,
            "errors": errors,
            "rolled_back": rolled_back,
            "parse_queue": pq,
            "transactions_in_db": tx_n,
        }
        if not rows and pq["pending"] == 0 and pq["parsed"] > 0:
            out["note"] = (
                "No pending parse-queue rows; existing rows are already PARSED. "
                "staging_rows_seen counts only PENDING rows processed in this request."
            )
        return out

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
            return _response(rolled_back=True)

    db.commit()
    return _response(rolled_back=False)
