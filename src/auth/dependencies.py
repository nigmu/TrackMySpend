import sqlite3
from pathlib import Path
from typing import Generator
from ..global_configs import DB_PATH


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI dependency — yields a SQLite connection with FK enforcement on,
    and row_factory set so rows behave like dicts.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()