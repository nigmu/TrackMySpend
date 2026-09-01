from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from psycopg import Connection

from ..core.config import GMAIL_SCOPES, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from ..core.crypto import decrypt_text, encrypt_text
from ..core.logging import get_logger
from . import db
from .oauth import authorization_url, exchange_code

logger = get_logger(__name__)


def start_connect() -> str:
    return authorization_url()


def complete_connect(code: str, state: str, conn: Connection) -> dict:
    creds = exchange_code(code, state)
    if not creds.token or not creds.refresh_token:
        raise RuntimeError("Google did not return access/refresh tokens")
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    email = service.users().getProfile(userId="me").execute()["emailAddress"]
    row = db.upsert_account(
        conn,
        email,
        encrypt_text(creds.token),
        encrypt_text(creds.refresh_token),
    )
    logger.info("gmail connected email=%s account_id=%s", email, row["id"])
    return {"status": "connected", "email": email, "account_id": row["id"]}


def list_accounts(conn: Connection) -> list[dict]:
    return db.list_accounts(conn)


def remove_account(conn: Connection, account_id: int) -> bool:
    if not db.delete_account(conn, account_id):
        return False
    logger.info("account removed account_id=%s", account_id)
    return True


def credentials_from_account(account: dict) -> Credentials:
    return Credentials(
        token=decrypt_text(account["oauth_access_token"]),
        refresh_token=decrypt_text(account["oauth_refresh_token"]),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=GMAIL_SCOPES,
    )
