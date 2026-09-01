import time

from google_auth_oauthlib.flow import Flow

from ..core.config import (
    GMAIL_SCOPES,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
)

# ponytail: in-memory PKCE store, lost on restart; upgrade to Redis if multi-worker
_pending: dict[str, tuple[str, float]] = {}
_TTL_SEC = 600


def _client_config() -> dict:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise RuntimeError("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not set")
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }
    }


def _new_flow() -> Flow:
    return Flow.from_client_config(
        _client_config(),
        scopes=GMAIL_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )


def authorization_url() -> str:
    flow = _new_flow()
    url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    verifier = flow.code_verifier
    if not state or not verifier:
        raise RuntimeError("OAuth flow did not produce state/code_verifier")
    _pending[state] = (verifier, time.monotonic())
    return url


def pop_code_verifier(state: str) -> str:
    now = time.monotonic()
    expired = [k for k, (_, t0) in _pending.items() if now - t0 > _TTL_SEC]
    for k in expired:
        _pending.pop(k, None)
    pair = _pending.pop(state, None)
    if not pair:
        raise ValueError("invalid or expired OAuth state")
    return pair[0]


def exchange_code(code: str, state: str):
    verifier = pop_code_verifier(state)
    flow = _new_flow()
    flow.code_verifier = verifier
    flow.fetch_token(code=code)
    return flow.credentials
