import json
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


def normalize_origin(url: str) -> str:
    raw = url.strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"origin needs http(s) scheme and host: {url!r}")
    if parsed.path not in ("", "/"):
        raise ValueError(f"origin must not include a path: {url!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def resolve_public_urls(
    public_host: str,
    api_public_base: str = "",
    frontend_origin: str = "",
) -> tuple[str, str, str]:
    """API base, UI origin, Google redirect. Explicit bases win over PUBLIC_HOST."""
    host = (public_host or "localhost").strip() or "localhost"
    if "://" in host or ":" in host:
        raise ValueError(f"PUBLIC_HOST must be host only (no scheme/port): {host!r}")
    api = (api_public_base or "").strip()
    fe = (frontend_origin or "").strip()
    api_out = normalize_origin(api) if api else f"http://{host}:2006"
    fe_out = normalize_origin(fe) if fe else f"http://{host}:2007"
    return api_out, fe_out, f"{api_out}/auth/gmail/callback"


def cors_allowlist(frontend_origin: str, extra: str = "") -> list[str]:
    origins = {
        frontend_origin,
        "http://localhost:2007",
        "http://127.0.0.1:2007",
    }
    for part in extra.split(","):
        piece = part.strip()
        if piece:
            origins.add(normalize_origin(piece))
    return sorted(origins)


PUBLIC_HOST = (os.environ.get("PUBLIC_HOST") or "localhost").strip() or "localhost"
API_PUBLIC_BASE, FRONTEND_ORIGIN, GOOGLE_REDIRECT_URI = resolve_public_urls(
    PUBLIC_HOST,
    os.environ.get("API_PUBLIC_BASE", ""),
    os.environ.get("FRONTEND_ORIGIN", ""),
)
CORS_ORIGINS = cors_allowlist(
    FRONTEND_ORIGIN,
    os.environ.get("CORS_EXTRA_ORIGINS", ""),
)

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
    """Ship API_PUBLIC_BASE to the static UI (js/env.js)."""
    _FRONTEND_ENV_JS.parent.mkdir(parents=True, exist_ok=True)
    payload = {"API_BASE": API_PUBLIC_BASE, "PUBLIC_HOST": PUBLIC_HOST}
    _FRONTEND_ENV_JS.write_text(
        f"window.__TMS_ENV__ = {json.dumps(payload)};\n",
        encoding="utf-8",
    )
    return _FRONTEND_ENV_JS


write_frontend_env()

assert GOOGLE_REDIRECT_URI == f"{API_PUBLIC_BASE}/auth/gmail/callback"
assert API_PUBLIC_BASE == normalize_origin(API_PUBLIC_BASE)
assert FRONTEND_ORIGIN == normalize_origin(FRONTEND_ORIGIN)
