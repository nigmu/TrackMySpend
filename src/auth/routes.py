"""HTTP route layer for Gmail auth.

This file defines auth endpoints and request parameters, then forwards
work to service-layer functions where the business logic lives.
"""

from fastapi import APIRouter, Depends
from psycopg import Connection

from .dependencies import get_db
from .service import (
    callback_service,
    connect_gmail_service,
    list_accounts_service,
    remove_account_service,
    update_active_service,
    update_polling_service,
)

router = APIRouter(prefix="/auth/gmail", tags=["Gmail Auth"])


@router.get("/connect")
def connect_gmail():
    """Start the Gmail OAuth flow and redirect the user to Google."""
    return connect_gmail_service()


@router.get("/callback")
def gmail_callback(code: str, state: str, db: Connection = Depends(get_db)):
    """Handle Google's OAuth callback and save/refresh account tokens."""
    return callback_service(code=code, state=state, db=db)


@router.get("/accounts")
def list_accounts(db: Connection = Depends(get_db)):
    """Return all Gmail accounts that are currently connected in the system."""
    return list_accounts_service(db=db)


@router.delete("/accounts/{account_id}")
def remove_account(account_id: int, db: Connection = Depends(get_db)):
    """Disconnect one Gmail account and remove it from local storage."""
    return remove_account_service(account_id=account_id, db=db)


@router.patch("/accounts/{account_id}/polling")
def update_polling(account_id: int, interval_min: int, db: Connection = Depends(get_db)):
    """Change how often a connected account should be polled for new mail."""
    return update_polling_service(account_id=account_id, interval_min=interval_min, db=db)


@router.patch("/accounts/{account_id}/active")
def update_active(account_id: int, is_active: bool, db: Connection = Depends(get_db)):
    """Enable or disable polling for a connected Gmail account."""
    return update_active_service(account_id=account_id, is_active=is_active, db=db)
