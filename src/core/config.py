import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# One knob for LAN/prod: set PUBLIC_HOST=192.168.x.x (or a hostname).
# Derives API URL, UI origin (CORS + OAuth return), and Google redirect.
PUBLIC_HOST = (os.environ.get("PUBLIC_HOST") or "localhost").strip() or "localhost"
API_PUBLIC_BASE = f"http://{PUBLIC_HOST}:2006"
FRONTEND_ORIGIN = f"http://{PUBLIC_HOST}:2007"
GOOGLE_REDIRECT_URI = f"{API_PUBLIC_BASE}/auth/gmail/callback"

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/trackmyspend",
)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_DIR = os.environ.get("LOG_DIR", "logs")
LOG_FILE_MAX_BYTES = int(os.environ.get("LOG_FILE_MAX_BYTES", "2000000"))
LOG_FILE_BACKUP_COUNT = int(os.environ.get("LOG_FILE_BACKUP_COUNT", "3"))
LOG_JSON = os.environ.get("LOG_JSON", "false").lower() in ("1", "true", "yes")
SMS_INGEST_TOKEN = os.environ.get("SMS_INGEST_TOKEN", "")

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BOOTSTRAP_MESSAGE_COUNT = 50
POLLER_TICK_SEC = 60
PARSE_BATCH_LIMIT = 200

_FRONTEND_ENV_JS = Path(__file__).resolve().parents[2] / "frontend" / "js" / "env.js"


def write_frontend_env() -> Path:
    """Ship PUBLIC_HOST-derived API base to the static UI (js/env.js)."""
    _FRONTEND_ENV_JS.parent.mkdir(parents=True, exist_ok=True)
    payload = {"API_BASE": API_PUBLIC_BASE, "PUBLIC_HOST": PUBLIC_HOST}
    _FRONTEND_ENV_JS.write_text(
        f"window.__TMS_ENV__ = {json.dumps(payload)};\n",
        encoding="utf-8",
    )
    return _FRONTEND_ENV_JS


write_frontend_env()

# ponytail: ceiling = trust PUBLIC_HOST has no scheme/port; upgrade = urlparse validation
assert "://" not in PUBLIC_HOST and ":" not in PUBLIC_HOST, PUBLIC_HOST
assert API_PUBLIC_BASE == f"http://{PUBLIC_HOST}:2006"
assert FRONTEND_ORIGIN == f"http://{PUBLIC_HOST}:2007"
assert GOOGLE_REDIRECT_URI == f"{API_PUBLIC_BASE}/auth/gmail/callback"
