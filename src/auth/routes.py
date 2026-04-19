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
    return connect_gmail_service()


@router.get("/callback")
def gmail_callback(code: str, state: str, db: Connection = Depends(get_db)):
    return callback_service(code=code, state=state, db=db)


@router.get("/accounts")
def list_accounts(db: Connection = Depends(get_db)):
    return list_accounts_service(db=db)


@router.delete("/accounts/{account_id}")
def remove_account(account_id: int, db: Connection = Depends(get_db)):
    return remove_account_service(account_id=account_id, db=db)


@router.patch("/accounts/{account_id}/polling")
def update_polling(account_id: int, interval_min: int, db: Connection = Depends(get_db)):
    return update_polling_service(account_id=account_id, interval_min=interval_min, db=db)


@router.patch("/accounts/{account_id}/active")
def update_active(account_id: int, is_active: bool, db: Connection = Depends(get_db)):
    return update_active_service(account_id=account_id, is_active=is_active, db=db)
