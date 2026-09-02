from psycopg import Connection

from ..core.amount import parse_amount_paisa
from ..core.config import PARSE_BATCH_LIMIT
from ..core.logging import get_logger
from ..logs.db import insert_event_log

logger = get_logger(__name__)


def parse_pending(conn: Connection, limit: int = PARSE_BATCH_LIMIT) -> dict:
    rows = conn.execute(
        """
        UPDATE raw_mail_data
        SET processing_status = 'processing', updated_at = NOW()
        WHERE id IN (
            SELECT id FROM raw_mail_data
            WHERE processing_status = 'pending'
            ORDER BY id
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, subject, snippet
        """,
        (limit,),
    ).fetchall()

    done = 0
    failed = 0
    for row in rows:
        text = f"{row['subject'] or ''} {row['snippet'] or ''}"
        amount = parse_amount_paisa(text)
        if amount is None:
            conn.execute(
                """
                UPDATE raw_mail_data
                SET processing_status = 'failed',
                    error_message = 'no amount found',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (row["id"],),
            )
            failed += 1
            continue
        conn.execute(
            """
            INSERT INTO transactions (raw_mail_id, amount_paisa)
            VALUES (%s, %s)
            ON CONFLICT (raw_mail_id) DO NOTHING
            """,
            (row["id"], amount),
        )
        conn.execute(
            """
            UPDATE raw_mail_data
            SET processing_status = 'done', error_message = NULL, updated_at = NOW()
            WHERE id = %s
            """,
            (row["id"],),
        )
        done += 1

    logger.info("parse finished claimed=%s done=%s failed=%s", len(rows), done, failed)
    if rows:
        event_type = "parse.failed" if failed and not done else "parse.completed"
        severity = "error" if failed and not done else "info"
        insert_event_log(
            event_type,
            "mail",
            f"Parse claimed={len(rows)} done={done} failed={failed}",
            severity=severity,
            context={"claimed": len(rows), "done": done, "failed": failed},
        )
    return {"claimed": len(rows), "done": done, "failed": failed}


def list_transactions(conn: Connection, limit: int = 50, offset: int = 0) -> list[dict]:
    return conn.execute(
        """
        SELECT t.id, t.raw_mail_id, t.amount_paisa, t.created_at,
               m.subject, m.snippet, m.sender, m.gmail_received_at
        FROM transactions t
        JOIN raw_mail_data m ON m.id = t.raw_mail_id
        ORDER BY t.id DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


def count_transactions(conn: Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()
    return int(row["n"]) if row else 0
