"""FastAPI dependencies used by auth routes.

This module provides request-scoped helpers, such as opening and closing
a database connection for each incoming API request.
"""

from collections.abc import Generator

from psycopg import Connection

from ..db_connection import connect


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
