import os
import base64
from cryptography.fernet import Fernet
from dotenv import load_dotenv, set_key
from pathlib import Path

load_dotenv()

ENV_PATH = Path(".env")


def _get_or_create_encryption_key() -> bytes:
    """
    Load encryption key from .env, or generate and save one on first run.
    """
    key = os.getenv("ENCRYPTION_KEY", "").strip()
    if not key:
        key = Fernet.generate_key().decode()
        set_key(str(ENV_PATH), "ENCRYPTION_KEY", key)
    return key.encode()


_fernet = Fernet(_get_or_create_encryption_key())


def encrypt_token(token: str) -> str:
    """Encrypt a token string for storage in DB."""
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt a token string retrieved from DB."""
    return _fernet.decrypt(encrypted.encode()).decode()


def get_oauth_config() -> dict:
    """Return the OAuth2 config dict expected by google-auth-oauthlib."""
    return {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]