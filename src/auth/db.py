"""Database helpers for the auth module.

Each function here performs one focused SQL operation on the
`email_accounts` table. These helpers do not contain HTTP or OAuth logic.
"""

from psycopg import Connection


def get_email_account_by_email(db: Connection, email_address: str) -> dict | None:
    """Fetch one account's id/active status by email address."""
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
    """Update encrypted OAuth tokens for an existing account and mark it active."""
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
    """Insert a brand-new connected Gmail account row."""
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
    """Return connected Gmail accounts ordered by creation time."""
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
    """Fetch a full account row by its internal account id."""
    row = db.execute(
        "SELECT * FROM email_accounts WHERE id = %s",
        (account_id,),
    ).fetchone()
    return row


def delete_email_account_by_id(db: Connection, account_id: int) -> None:
    """Delete one connected Gmail account by id."""
    db.execute("DELETE FROM email_accounts WHERE id = %s", (account_id,))


def update_email_account_polling_interval(db: Connection, account_id: int, interval_min: int) -> None:
    """Set a new polling interval (in minutes) for one account."""
    db.execute(
        "UPDATE email_accounts SET polling_interval_min = %s WHERE id = %s",
        (interval_min, account_id),
    )


def get_account_token_row(db: Connection, email_address: str) -> dict:
    """
    Return encrypted access and refresh tokens for one account email.

    Raises:
        ValueError: if no account exists for the given email address.
    """
    row = db.execute(
        """
        SELECT oauth_access_token, oauth_refresh_token
        FROM email_accounts
        WHERE email_address = %s
        """,
        (email_address,),
    ).fetchone()

    if not row:
        raise ValueError(f"No email_accounts row found for {email_address}.")
    return row


def update_email_account_active_status(db: Connection, account_id: int, is_active: bool) -> None:
    """Enable or disable an account without deleting its stored tokens."""
    db.execute(
        "UPDATE email_accounts SET is_active = %s WHERE id = %s",
        (is_active, account_id),
    )


def update_last_polled_at(db: Connection, account_id: int, when_iso: str) -> None:
    """Stamp the most recent successful poll for an account."""
    db.execute(
        "UPDATE email_accounts SET last_polled_at = %s WHERE id = %s",
        (when_iso, account_id),
    )


def update_last_history_id(db: Connection, account_id: int, history_id: str | None) -> None:
    """Persist the latest Gmail historyId so the next sync is incremental."""
    if not history_id:
        return
    db.execute(
        "UPDATE email_accounts SET last_history_id = %s WHERE id = %s",
        (history_id, account_id),
    )


def list_active_accounts(db: Connection) -> list[dict]:
    """Return active accounts with the fields needed for polling decisions."""
    rows = db.execute(
        """
        SELECT id, email_address, polling_interval_min, last_polled_at
        FROM email_accounts
        WHERE is_active = TRUE
        """
    ).fetchall()
    return list(rows)


def get_account_sync_state(db: Connection, account_id: int) -> dict | None:
    """Fetch the small slice of an account row used by the sync flow."""
    return db.execute(
        """
        SELECT id, email_address, is_active
        FROM email_accounts
        WHERE id = %s
        """,
        (account_id,),
    ).fetchone()
