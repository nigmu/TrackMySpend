from fastapi import APIRouter, HTTPException, Query

from .email_fetcher import (
    fetch_top_n_filtered_messages_for_one_account,
    fetch_top_n_raw_messages_for_one_account,
)
from .poller import (
    sync_latest_filtered_messages_for_all_accounts,
    sync_latest_filtered_messages_for_one_account,
)
router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


@router.get("/accounts/{account_id}/messages/raw/top-n")
def get_raw_messages_one_account_top_n(account_id: int, top_n: int = Query(default=10, ge=1, le=100)):
    """Raw messages - one account - top N."""
    messages = fetch_top_n_raw_messages_for_one_account(account_id=account_id, top_n=top_n)
    if not messages:
        raise HTTPException(
            status_code=404,
            detail="No messages found (account missing, inactive, or inbox empty).",
        )
    return {"account_id": account_id, "count": len(messages), "messages": messages}


@router.get("/accounts/{account_id}/messages/filtered/top-n")
def get_filtered_messages_one_account_top_n(account_id: int, top_n: int = Query(default=10, ge=1, le=100)):
    """Filtered messages - one account - top N."""
    messages = fetch_top_n_filtered_messages_for_one_account(account_id=account_id, top_n=top_n)
    if not messages:
        raise HTTPException(
            status_code=404,
            detail="No messages found (account missing, inactive, or inbox empty).",
        )
    return {"account_id": account_id, "count": len(messages), "messages": messages}


@router.get("/accounts/{account_id}/messages/filtered/latest")
def get_filtered_messages_one_account_latest(account_id: int):
    """Filtered messages - one account - latest (historyId incremental)."""
    result = sync_latest_filtered_messages_for_one_account(account_id=account_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Account not found.")
    if result["status"] == "inactive":
        raise HTTPException(status_code=400, detail="Account is inactive.")
    return result


@router.get("/accounts/messages/filtered/latest")
def get_filtered_messages_all_accounts_latest():
    """Filtered messages - all accounts - latest (historyId incremental)."""
    return sync_latest_filtered_messages_for_all_accounts()
