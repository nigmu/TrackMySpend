import sqlite3
from datetime import datetime, timezone
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from .gmail import encrypt_token, decrypt_token, get_oauth_config, GMAIL_SCOPES
from .dependencies import get_db

router = APIRouter(prefix="/auth/gmail", tags=["Gmail Auth"])

# Temporary in-memory PKCE state store for local/dev OAuth flow.
# Maps OAuth state -> (code_verifier, created_monotonic_time).
_oauth_pkce_store: dict[str, tuple[str, float]] = {}
_PKCE_STATE_TTL_SECONDS = 600


def _cleanup_stale_oauth_state() -> None:
    now = monotonic()
    stale_states = [
        state
        for state, (_, created_at) in _oauth_pkce_store.items()
        if now - created_at > _PKCE_STATE_TTL_SECONDS
    ]
    for state in stale_states:
        _oauth_pkce_store.pop(state, None)


def _get_or_create_local_user_id(db: sqlite3.Connection) -> int:
    """
    Return a local user id for single-user/dev mode.
    Creates a user row if none exists yet.
    """
    row = db.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
    if row:
        return int(row["id"])

    created_at = datetime.now(timezone.utc).isoformat()
    cursor = db.execute("INSERT INTO users (created_at) VALUES (?)", (created_at,))
    db.commit()
    return int(cursor.lastrowid)


def _build_flow(state: str | None = None) -> Flow:
    flow = Flow.from_client_config(
        get_oauth_config(),
        scopes=GMAIL_SCOPES,
        state=state,
    )
    flow.redirect_uri = get_oauth_config()["web"]["redirect_uris"][0]
    return flow


# ─────────────────────────────────────────
# Step 1 — Start OAuth flow
# GET /auth/gmail/connect
# Redirects user to Google consent screen.
# ─────────────────────────────────────────

@router.get("/connect")
def connect_gmail():
    _cleanup_stale_oauth_state()
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",   # ensures we get a refresh_token
        prompt="consent",        # forces consent screen so refresh_token is always returned
        include_granted_scopes="true",
    )
    if not flow.code_verifier:
        raise HTTPException(status_code=500, detail="OAuth PKCE setup failed: missing code verifier.")
    _oauth_pkce_store[state] = (flow.code_verifier, monotonic())
    return RedirectResponse(auth_url)


# ─────────────────────────────────────────
# Step 2 — Handle Google callback
# GET /auth/gmail/callback?code=...&state=...
# Exchanges code for tokens and saves to DB.
# ─────────────────────────────────────────

@router.get("/callback")
def gmail_callback(
    code: str,
    state: str,
    db: sqlite3.Connection = Depends(get_db),
):
    _cleanup_stale_oauth_state()
    state_entry = _oauth_pkce_store.pop(state, None)
    if not state_entry:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state. Please restart the Gmail connect flow.",
        )
    code_verifier, _ = state_entry

    try:
        flow = _build_flow(state=state)
        flow.code_verifier = code_verifier
        flow.fetch_token(code=code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {e}")

    credentials = flow.credentials
    user_id = _get_or_create_local_user_id(db)

    # Fetch the email address for this account using the userinfo endpoint
    try:
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        email_address = user_info.get("email")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch user info: {e}")

    if not email_address:
        raise HTTPException(status_code=400, detail="Could not retrieve email address from Google.")

    # Check if this account is already connected
    existing = db.execute(
        "SELECT id, is_active FROM email_accounts WHERE email_address = ?",
        (email_address,),
    ).fetchone()

    now = datetime.now(timezone.utc).isoformat()

    if existing:
        # Re-authorised — update tokens
        db.execute(
            """
            UPDATE email_accounts
            SET oauth_access_token  = ?,
                oauth_refresh_token = ?,
                is_active           = 1,
                last_polled_at      = NULL
            WHERE email_address = ?
            """,
            (
                encrypt_token(credentials.token),
                encrypt_token(credentials.refresh_token or ""),
                email_address,
            ),
        )
        db.commit()
        return JSONResponse({
            "status": "reconnected",
            "email": email_address,
            "message": f"{email_address} has been reconnected and tokens refreshed.",
        })

    # New account — insert
    db.execute(
        """
        INSERT INTO email_accounts
          (user_id, email_address, oauth_access_token, oauth_refresh_token,
           polling_interval_min, is_active, created_at)
        VALUES (?, ?, ?, ?, 60, 1, ?)
        """,
        (
            user_id,
            email_address,
            encrypt_token(credentials.token),
            encrypt_token(credentials.refresh_token or ""),
            now,
        ),
    )
    db.commit()

    return JSONResponse({
        "status": "connected",
        "email": email_address,
        "message": f"{email_address} connected successfully. Gmail readonly access granted.",
    })


# ─────────────────────────────────────────
# List all connected Gmail accounts
# GET /auth/gmail/accounts
# ─────────────────────────────────────────

@router.get("/accounts")
def list_accounts(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        """
        SELECT id, email_address, polling_interval_min,
               is_active, last_polled_at, created_at
        FROM email_accounts
        ORDER BY created_at ASC
        """
    ).fetchall()

    return [dict(row) for row in rows]


# ─────────────────────────────────────────
# Remove a connected Gmail account
# DELETE /auth/gmail/accounts/{account_id}
# Revokes Google token and deletes the row.
# ─────────────────────────────────────────

@router.delete("/accounts/{account_id}")
def remove_account(
    account_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    row = db.execute(
        "SELECT * FROM email_accounts WHERE id = ?", (account_id,)
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Account not found.")

    # Attempt to revoke the token at Google (best effort — don't fail if it errors)
    try:
        access_token = decrypt_token(row["oauth_access_token"])
        creds = Credentials(token=access_token)
        import requests
        requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": access_token},
            timeout=5,
        )
    except Exception:
        pass  # revocation failure should not block DB cleanup

    db.execute("DELETE FROM email_accounts WHERE id = ?", (account_id,))
    db.commit()

    return JSONResponse({
        "status": "removed",
        "email": row["email_address"],
        "message": f"{row['email_address']} has been disconnected.",
    })


# ─────────────────────────────────────────
# Update polling interval for an account
# PATCH /auth/gmail/accounts/{account_id}/polling
# ─────────────────────────────────────────

@router.patch("/accounts/{account_id}/polling")
def update_polling(
    account_id: int,
    interval_min: int,
    db: sqlite3.Connection = Depends(get_db),
):
    if interval_min < 5:
        raise HTTPException(status_code=400, detail="Polling interval must be at least 5 minutes.")

    row = db.execute(
        "SELECT id FROM email_accounts WHERE id = ?", (account_id,)
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Account not found.")

    db.execute(
        "UPDATE email_accounts SET polling_interval_min = ? WHERE id = ?",
        (interval_min, account_id),
    )
    db.commit()

    return JSONResponse({"status": "updated", "polling_interval_min": interval_min})