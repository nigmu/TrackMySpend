from pathlib import Path

from google.oauth2.credentials import Credentials

from src.security.crypto import decrypt_text

from .config import GMAIL_SCOPES, get_oauth_config
from .db import get_account_token_row

DB_PATH = Path("DB/data/trackmyspend.db")

def build_gmail_credentials_for_email(email_address: str, db_path: Path = DB_PATH) -> Credentials:
    """
    Build google.oauth2.credentials.Credentials from DB-stored encrypted tokens
    and OAuth client values loaded from .env.
    """
    row = get_account_token_row(email_address=email_address, db_path=db_path)
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