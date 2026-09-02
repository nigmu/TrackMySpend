from psycopg import Connection

from ..core.logging import get_logger

logger = get_logger(__name__)


def insert_mail(conn: Connection, account_id: int, msg: dict, rule: str) -> bool:
    row = conn.execute(
        """
        INSERT INTO raw_mail_data (
            email_account_id, gmail_message_id, gmail_thread_id,
            sender, subject, snippet, email_sent_at, gmail_received_at,
            matched_filter_rule
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (gmail_message_id) DO NOTHING
        RETURNING id
        """,
        (
            account_id,
            msg["gmail_message_id"],
            msg.get("gmail_thread_id"),
            msg.get("sender"),
            msg.get("subject"),
            msg.get("snippet"),
            msg.get("email_sent_at"),
            msg.get("gmail_received_at"),
            rule,
        ),
    ).fetchone()
    return row is not None


def list_mails(conn: Connection, limit: int = 50, offset: int = 0) -> list[dict]:
    return conn.execute(
        """
        SELECT m.*, a.email_address
        FROM raw_mail_data m
        JOIN email_accounts a ON a.id = m.email_account_id
        ORDER BY m.id DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


def count_mails(conn: Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM raw_mail_data").fetchone()
    return int(row["n"]) if row else 0


def start_sync_run(conn: Connection, account_id: int, trigger: str) -> int:
    row = conn.execute(
        """
        INSERT INTO sync_runs (account_id, trigger, status)
        VALUES (%s, %s, 'running')
        RETURNING id
        """,
        (account_id, trigger),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def finish_sync_run(
    conn: Connection,
    run_id: int,
    status: str,
    seen: int = 0,
    inserted: int = 0,
    skipped: int = 0,
    failed: int = 0,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE sync_runs
        SET finished_at = NOW(),
            status = %s,
            messages_seen = %s,
            inserted = %s,
            skipped = %s,
            failed = %s,
            error_message = %s
        WHERE id = %s
        """,
        (status, seen, inserted, skipped, failed, error_message, run_id),
    )
