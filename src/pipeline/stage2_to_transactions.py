"""Stage 2 -> Transactions: parse email bodies and insert into `transactions`.

Rows that cannot be classified as a known transaction type are marked SKIPPED
and do not block the rest of the run. Any other unexpected error triggers a
full rollback so no partial state is persisted.
"""

from __future__ import annotations

from psycopg import Connection

from ..ingestion.gmail_client import _extract_text_from_payload
from ..parsing import parse_text
from . import db as pipeline_db


def run_staging_to_transactions(db: Connection) -> dict:
    rows = pipeline_db.fetch_pending_stage2_rows(db)
    inserted = 0
    skipped = 0
    errors: list[str] = []

    def _response(*, rolled_back: bool) -> dict:
        pq = pipeline_db.parse_queue_etl_counts(db)
        tx_n = pipeline_db.count_transactions(db)
        tx_inserted = 0 if rolled_back else inserted
        out = {
            "staging_rows_seen": len(rows),
            "transactions_inserted": tx_inserted,
            "skipped": 0 if rolled_back else skipped,
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
            raw_payload_json = row.get("raw_payload_json") or {}
            payload = raw_payload_json.get("payload") or {}
            body_text = _extract_text_from_payload(payload) or row.get("snippet", "")
            parsed = parse_text(body_text)
            # amount is float INR from advanced parser (None for balance_update etc.)
            amount_raw = parsed.get("amount")
            transaction_amount = int(round((amount_raw or 0.0) * 100))
            extras = parsed.get("extras") or None
            pipeline_db.insert_transaction(
                db,
                parse_queue_id=row_id,
                transaction_type=parsed["type"],
                amount=transaction_amount,
                transaction_ts=row["email_sent_at"],
                bank=parsed.get("bank"),
                instrument=parsed.get("instrument"),
                channel=parsed.get("channel"),
                account_last4=parsed.get("account_last4"),
                counterparty=parsed.get("counterparty"),
                counterparty_vpa=parsed.get("counterparty_vpa"),
                reference_number=parsed.get("reference_number"),
                extras=extras,
            )
            pipeline_db.update_parse_status(db, row_id, "PARSED")
            inserted += 1
        except ValueError:
            # Email body could not be classified as a known transaction type
            # (e.g. marketing, security advisories). Mark SKIPPED and continue.
            pipeline_db.update_parse_status(db, row_id, "SKIPPED")
            skipped += 1
        except Exception as e:
            errors.append(f"stg id {row_id}: {e!s}")
            db.rollback()
            return _response(rolled_back=True)

    db.commit()
    return _response(rolled_back=False)
