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
    kind: Literal["debit", "credit", "bill_reminder"] | None = None
    amount_paisa: int | None = None
    instrument: str | None = None
    account_mask: str | None = None
    counterparty: str | None = None
    reference: str | None = None
    sms_received_at: datetime | None = None


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _require_amount(kind: str, amount: int | None) -> None:
    if kind != "bill_reminder" and amount is None:
        raise HTTPException(status_code=400, detail="amount_paisa is required")


def _write_fields(payload: ManualLedgerWrite) -> dict:
    data = payload.model_dump(exclude_unset=True)
    if "kind" in data and data["kind"] is None:
        raise HTTPException(status_code=400, detail="kind is required")
    if "sms_received_at" in data and data["sms_received_at"] is None:
        raise HTTPException(status_code=400, detail="sms_received_at is required")
    for key in ("instrument", "account_mask", "counterparty", "reference"):
        if key in data:
            data[key] = _blank(data[key])
    return data


@router.post("/sms/parse")
def parse_one_sms(payload: ParseSmsRequest, conn: Connection = Depends(get_db)):
    result = parse_stored_sms(conn, payload.raw_sms_id)
    if result is None:
        raise HTTPException(status_code=404, detail="raw sms not found")
    return {
        "raw_sms_id": payload.raw_sms_id,
        "processing_status": result.processing_status,
        "transaction": db.get_sms_transaction_by_raw(conn, payload.raw_sms_id),
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
    if payload.kind is None:
        raise HTTPException(status_code=400, detail="kind is required")
    fields = _write_fields(payload)
    _require_amount(payload.kind, fields.get("amount_paisa"))
    return db.insert_manual_ledger(
        conn,
        kind=payload.kind,
        amount_paisa=fields.get("amount_paisa"),
        instrument=fields.get("instrument"),
        account_mask=fields.get("account_mask"),
        counterparty=fields.get("counterparty"),
        reference=fields.get("reference"),
        sms_received_at=fields.get("sms_received_at"),
    )


@router.patch("/sms/transactions/{txn_id}")
def update_transaction(
    txn_id: int,
    payload: ManualLedgerWrite,
    conn: Connection = Depends(get_db),
):
    fields = _write_fields(payload)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    existing = db.get_sms_transaction(conn, txn_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    kind = fields.get("kind", existing["kind"])
    amount = fields["amount_paisa"] if "amount_paisa" in fields else existing["amount_paisa"]
    _require_amount(kind, amount)
    updated = db.update_sms_transaction(conn, txn_id, fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    return updated


@router.delete("/sms/transactions/{txn_id}")
def delete_transaction(txn_id: int, conn: Connection = Depends(get_db)):
    if not db.delete_sms_transaction(conn, txn_id):
        raise HTTPException(status_code=404, detail="transaction not found")
    return {"status": "deleted", "id": txn_id}
