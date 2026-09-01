from cryptography.fernet import Fernet

from .config import ENCRYPTION_KEY


def _fernet() -> Fernet:
    if not ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY is missing from the environment")
    return Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


def encrypt_text(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_text(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
