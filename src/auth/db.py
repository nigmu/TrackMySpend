from psycopg import Connection

from ..db_connection import connect


def get_email_account_by_email(db: Connection, email_address: str) -> dict | None:
    row = db.execute(
        "SELECT id, is_active FROM email_accounts WHERE email_address = %s",
        (email_address,),
    ).fetchone()
    return row


def update_email_account_tokens(
    db: Connection,
    email_address: str,
    encrypted_access_token: str,
    encrypted_refresh_token: str,
) -> None:
    db.execute(
        """
        UPDATE email_accounts
        SET oauth_access_token  = %s,
            oauth_refresh_token = %s,
            is_active           = TRUE,
            last_polled_at      = NULL
        WHERE email_address = %s
        """,
        (encrypted_access_token, encrypted_refresh_token, email_address),
    )


def insert_email_account(
    db: Connection,
    email_address: str,
    encrypted_access_token: str,
    encrypted_refresh_token: str,
    created_at: str,
) -> None:
    db.execute(
        """
        INSERT INTO email_accounts
          (email_address, oauth_access_token, oauth_refresh_token,
           polling_interval_min, is_active, created_at)
        VALUES (%s, %s, %s, 60, TRUE, %s)
        """,
        (email_address, encrypted_access_token, encrypted_refresh_token, created_at),
    )


def list_email_accounts(db: Connection) -> list[dict]:
    rows = db.execute(
        """
        SELECT id, email_address, polling_interval_min,
               is_active, last_polled_at, created_at
        FROM email_accounts
        ORDER BY created_at ASC
        """
    ).fetchall()
    return list(rows)


def get_email_account_by_id(db: Connection, account_id: int) -> dict | None:
    row = db.execute(
        "SELECT * FROM email_accounts WHERE id = %s",
        (account_id,),
    ).fetchone()
    return row


def delete_email_account_by_id(db: Connection, account_id: int) -> None:
    db.execute("DELETE FROM email_accounts WHERE id = %s", (account_id,))


def update_email_account_polling_interval(db: Connection, account_id: int, interval_min: int) -> None:
    db.execute(
        "UPDATE email_accounts SET polling_interval_min = %s WHERE id = %s",
        (interval_min, account_id),
    )


def select_account_token_row_by_email(db: Connection, email_address: str) -> dict | None:
    return db.execute(
        """
        SELECT oauth_access_token, oauth_refresh_token
        FROM email_accounts
        WHERE email_address = %s
        """,
        (email_address,),
    ).fetchone()


def get_account_token_row(email_address: str) -> dict:
    """
    Fetch encrypted token fields for a connected Gmail account.
    Raises ValueError if the account row is not found.
    """
    conn = connect()
    try:
        row = select_account_token_row_by_email(conn, email_address)
    finally:
        conn.close()

    if not row:
        raise ValueError(f"No email_accounts row found for {email_address}.")
    return row


def update_email_account_active_status(db: Connection, account_id: int, is_active: bool) -> None:
    db.execute(
        "UPDATE email_accounts SET is_active = %s WHERE id = %s",
        (is_active, account_id),
    )
