from collections.abc import Generator

from psycopg import Connection

from ..db_connection import connect


def get_db() -> Generator[Connection, None, None]:
    """
    FastAPI dependency — yields a PostgreSQL connection with dict-like rows.
    """
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
