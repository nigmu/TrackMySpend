from collections.abc import Generator

from psycopg import Connection, sql
from psycopg.rows import dict_row

from ..core.config import APP_TIMEZONE, DATABASE_URL


def connect() -> Connection:
    # Session clock is IST, so timestamptz values come back as +05:30.
    return Connection.connect(
        DATABASE_URL,
        row_factory=dict_row,
        autocommit=False,
        options=f"-c timezone={APP_TIMEZONE}",
    )


def set_database_timezone() -> None:
    """Default every client (psql, GUI) to IST. Applies to new sessions."""
    conn = Connection.connect(DATABASE_URL, autocommit=True)
    try:
        conn.execute(
            sql.SQL("ALTER DATABASE {} SET timezone TO {}").format(
                sql.Identifier(conn.info.dbname),
                sql.Literal(APP_TIMEZONE),
            )
        )
    finally:
        conn.close()


def get_db() -> Generator[Connection, None, None]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
