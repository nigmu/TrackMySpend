from collections.abc import Generator

from psycopg import Connection
from psycopg.rows import dict_row

from ..core.config import DATABASE_URL


def connect() -> Connection:
    return Connection.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)


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
