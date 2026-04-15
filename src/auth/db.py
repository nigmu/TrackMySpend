import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("DB/data/trackmyspend.db")


def get_email_account_by_email(db: sqlite3.Connection, email_address: str) -> sqlite3.Row | None:
    return db.execute(
        "SELECT id, is_active FROM email_accounts WHERE email_address = ?",
        (email_address,),
    ).fetchone()


def update_email_account_tokens(db: sqlite3.Connection, email_address: str, encrypted_access_token: str, encrypted_refresh_token: str) -> None:
    db.execute(
        """
        UPDATE email_accounts
        SET oauth_access_token  = ?,
            oauth_refresh_token = ?,
            is_active           = 1,
            last_polled_at      = NULL
        WHERE email_address = ?
        """,
        (encrypted_access_token, encrypted_refresh_token, email_address),
    )


def insert_email_account(db: sqlite3.Connection, email_address: str, encrypted_access_token: str, encrypted_refresh_token: str, created_at: str) -> None:
    db.execute(
        """
        INSERT INTO email_accounts
          (email_address, oauth_access_token, oauth_refresh_token,
           polling_interval_min, is_active, created_at)
        VALUES (?, ?, ?, 60, 1, ?)
        """,
        (email_address, encrypted_access_token, encrypted_refresh_token, created_at),
    )


def list_email_accounts(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT id, email_address, polling_interval_min,
               is_active, last_polled_at, created_at
        FROM email_accounts
        ORDER BY created_at ASC
        """
    ).fetchall()


def get_email_account_by_id(db: sqlite3.Connection, account_id: int) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM email_accounts WHERE id = ?",
        (account_id,),
    ).fetchone()


def delete_email_account_by_id(db: sqlite3.Connection, account_id: int) -> None:
    db.execute("DELETE FROM email_accounts WHERE id = ?", (account_id,))


def update_email_account_polling_interval(db: sqlite3.Connection, account_id: int, interval_min: int) -> None:
    db.execute(
        "UPDATE email_accounts SET polling_interval_min = ? WHERE id = ?",
        (interval_min, account_id),
    )


def select_account_token_row_by_email(db: sqlite3.Connection, email_address: str) -> sqlite3.Row | None:
    return db.execute(
        """
        SELECT oauth_access_token, oauth_refresh_token
        FROM email_accounts
        WHERE email_address = ?
        """,
        (email_address,),
    ).fetchone()


def get_account_token_row(email_address: str, db_path: Path = DB_PATH) -> sqlite3.Row:
    """
    Fetch encrypted token fields for a connected Gmail account from SQLite.
    Raises ValueError if the account row is not found.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = select_account_token_row_by_email(conn, email_address)
    finally:
        conn.close()

    if not row:
        raise ValueError(f"No email_accounts row found for {email_address}.")
    return row


def update_email_account_active_status(db: sqlite3.Connection, account_id: int, is_active: int) -> None:
    db.execute(
        "UPDATE email_accounts SET is_active = ? WHERE id = ?",
        (is_active, account_id),
    )