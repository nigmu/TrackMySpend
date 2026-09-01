from psycopg import Connection


def list_filters(conn: Connection) -> list[dict]:
    return conn.execute(
        "SELECT id, pattern, is_active, created_at FROM sender_filters ORDER BY id"
    ).fetchall()


def active_patterns(conn: Connection) -> list[str]:
    rows = conn.execute(
        "SELECT pattern FROM sender_filters WHERE is_active = TRUE ORDER BY id"
    ).fetchall()
    return [r["pattern"] for r in rows]


def add_filter(conn: Connection, pattern: str) -> dict:
    cleaned = pattern.strip().lower()
    if not cleaned:
        raise ValueError("pattern is empty")
    row = conn.execute(
        """
        INSERT INTO sender_filters (pattern)
        VALUES (%s)
        ON CONFLICT (pattern) DO UPDATE SET is_active = TRUE
        RETURNING id, pattern, is_active, created_at
        """,
        (cleaned,),
    ).fetchone()
    assert row is not None
    return row


def delete_filter(conn: Connection, filter_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM sender_filters WHERE id = %s RETURNING id",
        (filter_id,),
    )
    return cur.fetchone() is not None
