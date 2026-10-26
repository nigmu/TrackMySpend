from psycopg import Connection

from ..core.amount import parse_amount_paisa
from ..core.config import PARSE_BATCH_LIMIT
from ..core.logging import get_logger
from ..logs.db import insert_event_log

logger = get_logger(__name__)

# ponytail: message lists this many failed ids; the row's processing_status holds the rest.
# Upgrade path: query raw_mail_data where processing_status = 'failed'.
_PARSE_FAIL_ID_CAP = 20


def parse_event(claimed: int, done: int, failed_ids: list[int]) -> tuple[str, str, str]:
    """event_type, severity, message. Failed ids in the message are capped."""
    message = f"Parse claimed={claimed} done={done} failed={len(failed_ids)}"
    if failed_ids:
        shown = failed_ids[:_PARSE_FAIL_ID_CAP]
        extra = len(failed_ids) - len(shown)
        message += " ids=" + ",".join(str(i) for i in shown)
        if extra:
            message += f",+{extra}"
    if failed_ids and done == 0:
        return "parse.failed", "error", message
    if failed_ids:
        return "parse.completed", "warning", message
    return "parse.completed", "info", message


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
    failed_ids: list[int] = []
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
            failed_ids.append(int(row["id"]))
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

    event_type, severity, message = parse_event(len(rows), done, failed_ids)
    getattr(logger, severity)(message)
    if rows:
        context = {"claimed": len(rows), "done": done, "failed": len(failed_ids)}
        if failed_ids:
            context["failed_ids"] = failed_ids[:_PARSE_FAIL_ID_CAP]
        insert_event_log(
            event_type,
            "mail",
            message,
            severity=severity,
            context=context,
        )
    return {"claimed": len(rows), "done": done, "failed": len(failed_ids)}


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
