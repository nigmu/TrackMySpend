"""FastAPI request-scoped database dependency."""

from collections.abc import Generator

from psycopg import Connection

from .connection import connect


def get_db() -> Generator[Connection, None, None]:
    """
    Provide a database connection for a single request.

    FastAPI calls this for each request that needs `db`, then guarantees
    the connection is closed after the response is sent.
    """
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
