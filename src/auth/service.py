"""Business logic for Gmail OAuth and account management.

This module runs the full connect/callback flow, stores encrypted tokens,
and handles account maintenance actions such as remove, polling updates,
and active/inactive toggles.
"""

from src.core.logging import get_logger

logger = get_logger(__name__)


from datetime import datetime, timezone
from time import monotonic

from fastapi import HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from psycopg import Connection
from src.security.crypto import decrypt_text, encrypt_text

from .config import GMAIL_SCOPES, get_oauth_config
from .db import (
    delete_email_account_by_id,
    get_email_account_by_email,
    get_email_account_by_id,
    insert_email_account,
    list_email_accounts,
    update_email_account_active_status,
    update_email_account_polling_interval,
    update_email_account_tokens,
)

_oauth_pkce_store: dict[str, tuple[str, float]] = {}
_PKCE_STATE_TTL_SECONDS = 600


def _error_type_name(err: Exception) -> str:
    """Return a short exception class name for safe diagnostics."""
    return type(err).__name__


def _cleanup_stale_oauth_state() -> None:
    """Drop expired OAuth state entries from temporary in-memory storage."""
    now = monotonic()
    stale_states = [
        state
        for state, (_, created_at) in _oauth_pkce_store.items()
        if now - created_at > _PKCE_STATE_TTL_SECONDS
    ]
    for state in stale_states:
        _oauth_pkce_store.pop(state, None)


def _build_flow(state: str | None = None) -> Flow:
    """Create a Google OAuth flow object configured for this app."""
    flow = Flow.from_client_config(
        get_oauth_config(),
        scopes=GMAIL_SCOPES,
        state=state,
    )
    flow.redirect_uri = get_oauth_config()["web"]["redirect_uris"][0]
    return flow


def connect_gmail_service() -> RedirectResponse:
    """Start OAuth login and redirect the user to Google's consent screen."""
    logger.info("gmail_connect_started")
    _cleanup_stale_oauth_state()
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    if not flow.code_verifier:
        logger.error("gmail_connect_pkce_missing_verifier")
        raise HTTPException(status_code=500, detail="OAuth PKCE setup failed: missing code verifier.")

    _oauth_pkce_store[state] = (flow.code_verifier, monotonic())
    logger.info("gmail_connect_redirect_ready pkce_store_size=%s", len(_oauth_pkce_store))
    return RedirectResponse(auth_url)


def callback_service(code: str, state: str, db: Connection) -> JSONResponse:
    """Complete OAuth callback and persist encrypted tokens for the account."""
    logger.info("gmail_callback_received")
    _cleanup_stale_oauth_state()
    state_entry = _oauth_pkce_store.pop(state, None)
    if not state_entry:
        logger.warning("gmail_callback_invalid_or_expired_state")
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state. Please restart the Gmail connect flow.",
        )

    code_verifier, _ = state_entry

    try:
        flow = _build_flow(state=state)
        flow.code_verifier = code_verifier
        flow.fetch_token(code=code)
        logger.info("gmail_token_exchange_success")
    except Exception as e:
        logger.error("gmail_token_exchange_failed error_type=%s", _error_type_name(e))
        raise HTTPException(status_code=400, detail="OAuth token exchange failed.")

    credentials = flow.credentials

    try:
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        email_address = user_info.get("email")
    except Exception as e:
        logger.error("gmail_userinfo_fetch_failed error_type=%s", _error_type_name(e))
        raise HTTPException(status_code=400, detail="Failed to fetch user info.")

    if not email_address:
        logger.warning("gmail_userinfo_missing_email")
        raise HTTPException(status_code=400, detail="Could not retrieve email address from Google.")

    encrypted_access = encrypt_text(credentials.token)
    encrypted_refresh = encrypt_text(credentials.refresh_token or "")

    existing = get_email_account_by_email(db, email_address)
    if existing:
        update_email_account_tokens(db, email_address, encrypted_access, encrypted_refresh)
        db.commit()
        logger.info("gmail_account_reconnected account_id=%s", existing["id"])
        return JSONResponse(
            {
                "status": "reconnected",
                "email": email_address,
                "message": f"{email_address} has been reconnected and tokens refreshed.",
            }
        )

    now = datetime.now(timezone.utc).isoformat()
    insert_email_account(db, email_address, encrypted_access, encrypted_refresh, now)
    db.commit()
    logger.info("gmail_account_connected")
    return JSONResponse(
        {
            "status": "connected",
            "email": email_address,
            "message": f"{email_address} connected successfully. Gmail readonly access granted.",
        }
    )



def list_accounts_service(db: Connection) -> list[dict]:
    """List all connected Gmail accounts in API-ready dictionary form."""
    rows = list_email_accounts(db)
    logger.info("gmail_accounts_listed count=%s", len(rows))
    return [dict(row) for row in rows]


def remove_account_service(account_id: int, db: Connection) -> JSONResponse:
    """Disconnect and delete one connected Gmail account by id."""
    logger.info("gmail_account_remove_requested account_id=%s", account_id)
    row = get_email_account_by_id(db, account_id)
    if not row:
        logger.warning("gmail_account_remove_not_found account_id=%s", account_id)
        raise HTTPException(status_code=404, detail="Account not found.")

    try:
        access_token = decrypt_text(row["oauth_access_token"])
        import requests
        requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": access_token},
            timeout=5,
        )
        logger.info("gmail_token_revoke_attempted account_id=%s", account_id)
    except Exception as e:
        logger.error("gmail_token_revoke_failed account_id=%s error_type=%s", account_id, _error_type_name(e))

    delete_email_account_by_id(db, account_id)
    db.commit()
    logger.info("gmail_account_removed account_id=%s", account_id)
    return JSONResponse(
        {
            "status": "removed",
            "email": row["email_address"],
            "message": f"{row['email_address']} has been disconnected.",
        }
    )



def update_polling_service(account_id: int, interval_min: int, db: Connection) -> JSONResponse:
    """Update how often one account should be polled for new emails."""
    logger.info("gmail_polling_update_requested account_id=%s interval_min=%s", account_id, interval_min)
    if interval_min < 5:
        logger.warning("gmail_polling_update_invalid_interval account_id=%s interval_min=%s", account_id, interval_min)
        raise HTTPException(status_code=400, detail="Polling interval must be at least 5 minutes.")

    row = get_email_account_by_id(db, account_id)
    if not row:
        logger.warning("gmail_polling_update_not_found account_id=%s", account_id)
        raise HTTPException(status_code=404, detail="Account not found.")

    update_email_account_polling_interval(db, account_id, interval_min)
    db.commit()
    logger.info("gmail_polling_updated account_id=%s interval_min=%s", account_id, interval_min)
    return JSONResponse({"status": "updated", "polling_interval_min": interval_min})


def update_active_service(account_id: int, is_active: bool, db: Connection) -> JSONResponse:
    """Enable or disable a connected account without deleting its data."""
    logger.info("gmail_active_update_requested account_id=%s is_active=%s", account_id, bool(is_active))
    row = get_email_account_by_id(db, account_id)
    if not row:
        logger.warning("gmail_active_update_not_found account_id=%s", account_id)
        raise HTTPException(status_code=404, detail="Account not found.")

    update_email_account_active_status(db, account_id, is_active)
    db.commit()
    logger.info("gmail_active_updated account_id=%s is_active=%s", account_id, bool(is_active))

    return JSONResponse(
        {
            "status": "updated",
            "account_id": account_id,
            "is_active": bool(is_active),
        }
    )
