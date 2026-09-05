from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg import Connection
from pydantic import BaseModel

from ..core.config import SMS_INGEST_TOKEN
from ..core.logging import get_logger
from ..db.connection import get_db
from ..logs.db import insert_event_log
from . import db

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


@router.post("/sms/ingest")
def ingest_sms(
    payload: SmsIngestRequest,
    conn: Connection = Depends(get_db),
    _: None = Depends(require_sms_token),
):
    try:
        row_id, inserted = db.insert_sms(
            conn,
            sender=payload.sender,
            body=payload.body,
            received_at=payload.received_at,
            device_id=payload.device_id,
        )
    except Exception:
        logger.exception(
            "sms ingest insert failed sender=%s message_id=%s",
            payload.sender,
            payload.message_id,
        )
        insert_event_log(
            "sms.ingest_failed",
            "sms",
            "SMS ingest insert failed",
            severity="error",
            context={
                "message_id": payload.message_id,
                "sender": payload.sender,
                "device_id": payload.device_id,
            },
        )
        raise
    if inserted:
        logger.info(
            "sms ingest accepted id=%s sender=%s message_id=%s",
            row_id,
            payload.sender,
            payload.message_id,
        )
        insert_event_log(
            "sms.ingest_accepted",
            "sms",
            f"SMS ingested id={row_id}",
            context={
                "id": row_id,
                "message_id": payload.message_id,
                "sender": payload.sender,
                "device_id": payload.device_id,
            },
        )
    else:
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
    return {"status": "ok", "id": row_id, "duplicate": not inserted}


@router.get("/sms/latest-received-at")
def get_latest_received_at(
    device_id: str = Query(min_length=1),
    conn: Connection = Depends(get_db),
    _: None = Depends(require_sms_token),
):
    latest = db.latest_received_at(conn, device_id)
    insert_event_log(
        "sms.watermark_fetched",
        "sms",
        "SMS watermark fetched",
        context={"device_id": device_id, "received_at": latest.isoformat() if latest else None},
    )
    return {"received_at": latest.isoformat() if latest else None}


@router.get("/sms")
def get_sms(
    conn: Connection = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items = db.list_sms(conn, limit=limit, offset=offset)
    return {"count": len(items), "total": db.count_sms(conn), "sms": items}
