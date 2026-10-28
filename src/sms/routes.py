from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg import Connection
from pydantic import BaseModel, ConfigDict

from ..core.config import SMS_INGEST_TOKEN
from ..core.logging import get_logger
from ..db.connection import get_db
from ..logs.db import insert_event_log
from . import db
from .classify import parse_new_sms, parse_stored_sms
from . import ledger
from .ledger import LedgerRuleError

logger = get_logger(__name__)
router = APIRouter(tags=["SMS"])


class SmsIngestRequest(BaseModel):
    message_id: str | None = None
    sender: str | None = None
    body: str
    received_at: datetime | None = None
    device_id: str | None = None


def require_sms_token(x_trackmyspend_token: str | None = Header(default=None)) -> None:
    if not SMS_INGEST_TOKEN:
        return
    if x_trackmyspend_token != SMS_INGEST_TOKEN:
        logger.warning("sms ingest rejected reason=invalid_token")
        raise HTTPException(status_code=401, detail="invalid ingest token")


@router.post("/sms/ingest_and_parse")
def ingest_and_parse_sms(
    payload: SmsIngestRequest,
    conn: Connection = Depends(get_db),
    _: None = Depends(require_sms_token),
):
    try:
        row_id = None
        row_id, inserted = db.insert_sms(
            conn,
            sender=payload.sender,
            body=payload.body,
            received_at=payload.received_at,
            device_id=payload.device_id,
        )
        if not inserted:
            logger.info(
                "sms ingest duplicate id=%s sender=%s message_id=%s",
                row_id,
                payload.sender,
                payload.message_id,
            )
            insert_event_log(
                "sms.ingest_duplicate",
                "sms",
                f"SMS duplicate skipped id={row_id}",
                context={
                    "id": row_id,
                    "message_id": payload.message_id,
                    "sender": payload.sender,
                    "device_id": payload.device_id,
                },
            )
            return {"status": "ok", "id": row_id, "duplicate": True}
        result = parse_new_sms(conn, row_id, payload.body)
    except Exception:
        logger.exception(
            "sms ingest failed id=%s sender=%s message_id=%s",
            row_id,
            payload.sender,
            payload.message_id,
        )
        insert_event_log(
            "sms.ingest_failed",
            "sms",
            "SMS ingest failed" if row_id is None else f"SMS ingest failed id={row_id}",
            severity="error",
            context={
                "id": row_id,
                "message_id": payload.message_id,
                "sender": payload.sender,
                "device_id": payload.device_id,
            },
        )
        raise
    template = result.template or result.category_id or "none"
    reason = result.reason or "none"
    log = logger.warning if result.processing_status == "unmatched" else logger.info
    log(
        "sms ingest accepted id=%s sender=%s message_id=%s processing_status=%s template=%s reason=%s",
        row_id,
        payload.sender,
        payload.message_id,
        result.processing_status,
        template,
        reason,
    )
    insert_event_log(
        "sms.ingest_accepted",
        "sms",
        (
            f"SMS ingested id={row_id} processing_status={result.processing_status}"
            f" template={template} reason={reason}"
        ),
        severity="warning" if result.processing_status == "unmatched" else "info",
        context={
            "id": row_id,
            "message_id": payload.message_id,
            "sender": payload.sender,
            "device_id": payload.device_id,
            "processing_status": result.processing_status,
            "template": template,
            "reason": reason,
        },
    )
    return {
        "status": "ok",
        "id": row_id,
        "duplicate": False,
        "processing_status": result.processing_status,
    }


class ParseSmsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_sms_id: int


class ManualLedgerWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["debit", "credit", "bill_reminder", "balance"] | None = None
    amount_paisa: int | None = None
    instrument: str | None = None
    account_mask: str | None = None
    counterparty: str | None = None
    reference: str | None = None
    sms_received_at: datetime | None = None


@router.post("/sms/parse")
def parse_one_sms(payload: ParseSmsRequest, conn: Connection = Depends(get_db)):
    result = parse_stored_sms(conn, payload.raw_sms_id)
    if result is None:
        raise HTTPException(status_code=404, detail="raw sms not found")
    return {
        "raw_sms_id": payload.raw_sms_id,
        "processing_status": result.processing_status,
        "transaction": ledger.get_by_raw(conn, payload.raw_sms_id),
    }


@router.get("/sms/latest-received-at")
def get_latest_received_at(
    device_id: str = Query(min_length=1),
    conn: Connection = Depends(get_db),
    _: None = Depends(require_sms_token),
):
    latest = db.latest_received_at(conn, device_id)
    return {"received_at": latest.isoformat() if latest else None}


@router.get("/sms")
def get_sms(
    conn: Connection = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items = db.list_sms(conn, limit=limit, offset=offset)
    return {"count": len(items), "total": db.count_sms(conn), "sms": items}


@router.get("/sms/transactions")
def get_sms_transactions(
    conn: Connection = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items = db.list_sms_transactions(conn, limit=limit, offset=offset)
    return {"count": len(items), "total": db.count_sms_transactions(conn), "transactions": items}


@router.post("/sms/transactions")
def create_manual_transaction(payload: ManualLedgerWrite, conn: Connection = Depends(get_db)):
    try:
        return ledger.create_manual(conn, payload.model_dump(exclude_unset=True))
    except LedgerRuleError as err:
        raise HTTPException(status_code=400, detail=err.detail) from err


@router.patch("/sms/transactions/{txn_id}")
def update_transaction(
    txn_id: int,
    payload: ManualLedgerWrite,
    conn: Connection = Depends(get_db),
):
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    try:
        updated = ledger.update(conn, txn_id, fields)
    except LedgerRuleError as err:
        raise HTTPException(status_code=400, detail=err.detail) from err
    if updated is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    return updated


@router.delete("/sms/transactions/{txn_id}")
def delete_transaction(txn_id: int, conn: Connection = Depends(get_db)):
    if not ledger.delete(conn, txn_id):
        raise HTTPException(status_code=404, detail="transaction not found")
    return {"status": "deleted", "id": txn_id}
