"""CLI entry point: create or align schema against the configured database.

Run with:
    python -m src.db.migrate
"""

import psycopg

from ..core.config import DATABASE_URL
from .schema import SCHEMA_STATEMENTS


def create_db() -> None:
    conn = psycopg.connect(DATABASE_URL)
    try:
        conn.autocommit = True
        info = conn.info
        print(
            "Connected: "
            f"dbname={info.dbname!r} host={info.host!r} port={info.port} user={info.user!r}"
        )
        with conn.cursor() as cur:
            for stmt in SCHEMA_STATEMENTS:
                cur.execute(stmt.strip())
            cur.execute(
                """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
            tables = [row[0] for row in cur.fetchall()]
        print("Tables in schema public:", ", ".join(tables) if tables else "(none)")
    finally:
        conn.close()


if __name__ == "__main__":
    create_db()
