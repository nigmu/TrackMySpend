from psycopg import Connection


def list_accounts(conn: Connection) -> list[dict]:
    return conn.execute(
        """
        SELECT id, email_address, is_active, polling_interval_min,
               last_polled_at, last_history_id, created_at, updated_at
        FROM email_accounts
        ORDER BY id
        """
    ).fetchall()


def get_account(conn: Connection, account_id: int) -> dict | None:
    return conn.execute(
        "SELECT * FROM email_accounts WHERE id = %s",
        (account_id,),
    ).fetchone()


def list_active_accounts(conn: Connection) -> list[dict]:
    return conn.execute(
        "SELECT * FROM email_accounts WHERE is_active = TRUE ORDER BY id"
    ).fetchall()


def list_due_accounts(conn: Connection) -> list[dict]:
    return conn.execute(
        """
        SELECT * FROM email_accounts
        WHERE is_active = TRUE
          AND (
            last_polled_at IS NULL
            OR last_polled_at <= NOW() - (polling_interval_min * INTERVAL '1 minute')
          )
        ORDER BY id
        """
    ).fetchall()


def upsert_account(
    conn: Connection,
    email_address: str,
    access_token_enc: str,
    refresh_token_enc: str,
) -> dict:
    row = conn.execute(
        """
        INSERT INTO email_accounts (email_address, oauth_access_token, oauth_refresh_token)
        VALUES (%s, %s, %s)
        ON CONFLICT (email_address) DO UPDATE SET
            oauth_access_token = EXCLUDED.oauth_access_token,
            oauth_refresh_token = EXCLUDED.oauth_refresh_token,
            is_active = TRUE,
            updated_at = NOW()
        RETURNING id, email_address
        """,
        (email_address, access_token_enc, refresh_token_enc),
    ).fetchone()
    assert row is not None
    return row


def delete_account(conn: Connection, account_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM email_accounts WHERE id = %s RETURNING id",
        (account_id,),
    )
    return cur.fetchone() is not None


def update_sync_state(
    conn: Connection,
    account_id: int,
    last_history_id: int | None,
) -> None:
    conn.execute(
        """
        UPDATE email_accounts
        SET last_history_id = %s, last_polled_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (last_history_id, account_id),
    )
