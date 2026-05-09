from __future__ import annotations

from psycopg import Connection

from ..parsing.basic_transactions_parser import parse_text


def update_parse_status(db: Connection, row_id: int) -> bool:
    try:
        q = """
        UPDATE email_parse_queue_staging
        SET parse_status = 'PARSED'
        WHERE id = %s
        """
        db.execute(q, (row_id,))
    except Exception as e:
        print(f"Error updating parse status: {e}")
        return False
    return True


def fetch_raw_text_from_table(db: Connection) -> list[dict]:
    q = """
    SELECT id, snippet, date_header
    FROM email_parse_queue_staging
    WHERE parse_status IS NULL
    ORDER BY id ASC
    """
    return list(db.execute(q).fetchall())


def insert_into_transactions_table(
    db: Connection,
    row_id: int,
    transaction_type: str,
    transaction_amount: int,
    transaction_date,
) -> None:
    q = """
    INSERT INTO transactions (stg2_id, transaction_type, amount, transaction_date)
    VALUES (%s, %s, %s, %s)
    """
    db.execute(q, (row_id, transaction_type, transaction_amount, transaction_date))


def run_staging_to_transactions(db: Connection) -> dict:
    """Parse staging snippets and insert rows into `transactions` (including Not a Transaction / 0)."""
    rows = fetch_raw_text_from_table(db)
    inserted = 0
    errors: list[str] = []

    for row in rows:
        row_id = row["id"]
        try:
            parsed = parse_text(row["snippet"])
            transaction_type = parsed["type"]
            transaction_amount = parsed["amount"]
            transaction_date = row["date_header"]
            insert_into_transactions_table(
                db, row_id, transaction_type, int(transaction_amount), transaction_date
            )
            if not update_parse_status(db, row_id):
                errors.append(f"stg id {row_id}: failed to set parse_status to PARSED")
                db.rollback()
                return {
                    "staging_rows_seen": len(rows),
                    "transactions_inserted": 0,
                    "errors": errors,
                    "rolled_back": True,
                }
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


def segment_data(db: Connection) -> dict:
    """Backward-compatible alias; prefer `run_staging_to_transactions`."""
    return run_staging_to_transactions(db)
