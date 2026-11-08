from psycopg.types.json import Json

from ..core.logging import get_logger
from ..db.connection import connect

logger = get_logger(__name__)


def insert_event_log(
    event_type: str,
    source: str,
    message: str,
    severity: str = "info",
    context: dict | None = None,
) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO app_event_logs (event_type, source, severity, message, context)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (event_type, source, severity, message, Json(context or {})),
        )
        conn.commit()
    except Exception:
        # Best-effort: a failure to write to the event log must never break
        # the caller's real operation. Log it
        # to the file logger instead of raising.
        conn.rollback()
        logger.exception("event log insert failed type=%s source=%s", event_type, source)
    finally:
        conn.close()


def list_event_logs(conn, limit: int = 50, offset: int = 0) -> list[dict]:
    return conn.execute(
        """
        SELECT id, event_type, source, severity, message, context, created_at
        FROM app_event_logs
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


def count_event_logs(conn) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM app_event_logs").fetchone()
    return int(row["n"]) if row else 0
