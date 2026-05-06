"""Credential builder for Gmail API calls.

This file reads encrypted OAuth tokens from the database, decrypts them,
and returns a Google Credentials object that other modules can use.
"""

from psycopg import Connection
from google.oauth2.credentials import Credentials

from src.security.crypto import decrypt_text

from .config import GMAIL_SCOPES, get_oauth_config
from .db import get_account_token_row


def build_gmail_credentials_for_email(db: Connection, email_address: str) -> Credentials:
    """
    Create Gmail credentials for one connected email account.

    It fetches encrypted tokens from the database, decrypts them, and
    combines them with OAuth client settings from environment variables.
    """
    row = get_account_token_row(db, email_address=email_address)
    access_token = decrypt_text(row["oauth_access_token"])
    refresh_token = decrypt_text(row["oauth_refresh_token"])
    oauth = get_oauth_config()["web"]

    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=oauth["token_uri"],
        client_id=oauth["client_id"],
        client_secret=oauth["client_secret"],
        scopes=GMAIL_SCOPES,
    )
