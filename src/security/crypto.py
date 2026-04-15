import os
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import load_dotenv, set_key

# Load environment variables from .env file to os.environ(memory)
load_dotenv()

ENV_PATH = Path(".env")



def _normalize_env_value(value: str) -> str:
    # Handles quoted values like 'abc' or "abc" in .env
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _get_or_create_fernet_key(env_var_name: str = "ENCRYPTION_KEY", env_path: Path = ENV_PATH) -> bytes:
    """
    Return a valid Fernet key from environment, but if not present, create one and save it to the .env file.
    """
    key = _normalize_env_value(os.getenv(env_var_name, ""))
    if not key:
        key = Fernet.generate_key().decode()
        set_key(str(env_path), env_var_name, key)
    return key.encode()


# Create ONCE at module load
_FERNET = Fernet(_get_or_create_fernet_key())


def encrypt_text(plaintext: str, env_var_name: str = "ENCRYPTION_KEY") -> str:
    """Encrypt text and return a URL-safe token string."""
    return _FERNET.encrypt(plaintext.encode()).decode()


def decrypt_text(ciphertext: str, env_var_name: str = "ENCRYPTION_KEY") -> str:
    """Decrypt a token string and return plaintext."""
    return _FERNET.decrypt(ciphertext.encode()).decode()