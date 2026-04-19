from collections.abc import Generator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from .global_configs import DATABASE_URL


def connect() -> Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def get_connection() -> Generator[Connection, None, None]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
