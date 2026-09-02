import os
from datetime import datetime

from dotenv import load_dotenv
from psycopg import Connection

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

RAW_SMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_sms (
    id BIGSERIAL PRIMARY KEY,
    sender TEXT,
    body TEXT NOT NULL,
    received_at TIMESTAMPTZ,
    device_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def connect() -> Connection:
    return Connection.connect(DATABASE_URL, autocommit=False)


def init_schema() -> None:
    with connect() as conn:
        conn.execute(RAW_SMS_SCHEMA)
        conn.commit()


def insert_sms(
    sender: str | None,
    body: str,
    received_at: datetime | None,
    device_id: str | None,
) -> int:
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO raw_sms (sender, body, received_at, device_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (sender, body, received_at, device_id),
        ).fetchone()
        conn.commit()
        return row[0]
