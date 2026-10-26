from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from psycopg import Connection

from ..core.config import FRONTEND_ORIGIN
from ..core.logging import get_logger
from ..db.connection import get_db
from . import service

logger = get_logger(__name__)
router = APIRouter(tags=["Accounts"])


@router.get("/auth/gmail/connect")
def connect_gmail():
    try:
        url = service.start_connect()
    except Exception as exc:
        logger.exception("oauth connect failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url)


@router.get("/auth/gmail/callback")
def gmail_callback(
    code: str,
    state: str,
    db: Connection = Depends(get_db),
):
    try:
        result = service.complete_connect(code, state, db)
    except ValueError as exc:
        logger.warning("oauth callback rejected reason=%s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("oauth callback failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    email = result["email"]
    return RedirectResponse(f"{FRONTEND_ORIGIN}/?connected={email}")


@router.get("/accounts")
def get_accounts(db: Connection = Depends(get_db)):
    return service.list_accounts(db)


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Connection = Depends(get_db)):
    if not service.remove_account(db, account_id):
        raise HTTPException(status_code=404, detail="account not found")
    return {"status": "deleted", "account_id": account_id}
