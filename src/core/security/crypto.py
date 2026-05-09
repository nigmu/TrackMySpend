"""Symmetric encryption helpers for sensitive values (e.g. OAuth tokens).

The Fernet key is read from the `ENCRYPTION_KEY` environment variable. If
missing, a new key is generated and persisted into `.env` automatically.
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv, set_key

load_dotenv()

ENV_PATH = Path(".env")


def _normalize_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _get_or_create_fernet_key(env_var_name: str = "ENCRYPTION_KEY", env_path: Path = ENV_PATH) -> bytes:
    """Return a valid Fernet key from environment, creating one if missing."""
    key = _normalize_env_value(os.getenv(env_var_name, ""))
    if not key:
        key = Fernet.generate_key().decode()
        set_key(str(env_path), env_var_name, key)
    return key.encode()


_FERNET = Fernet(_get_or_create_fernet_key())


def encrypt_text(plaintext: str, env_var_name: str = "ENCRYPTION_KEY") -> str:
    return _FERNET.encrypt(plaintext.encode()).decode()


def decrypt_text(ciphertext: str, env_var_name: str = "ENCRYPTION_KEY") -> str:
    return _FERNET.decrypt(ciphertext.encode()).decode()
