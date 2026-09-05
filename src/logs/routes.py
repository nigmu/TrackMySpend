from fastapi import APIRouter, Depends, Query
from psycopg import Connection
from pydantic import BaseModel, Field

from ..db.connection import get_db
from ..sms.routes import require_sms_token
from . import db
from .db import insert_event_log

router = APIRouter(tags=["Logs"])


class CompanionEventRequest(BaseModel):
    event_type: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = "info"
    context: dict | None = None


@router.get("/logs")
def get_logs(
    conn: Connection = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items = db.list_event_logs(conn, limit=limit, offset=offset)
    return {"count": len(items), "total": db.count_event_logs(conn), "logs": items}


@router.post("/logs/event")
def post_companion_event(
    payload: CompanionEventRequest,
    _: None = Depends(require_sms_token),
):
    insert_event_log(
        payload.event_type,
        "companion",
        payload.message,
        severity=payload.severity,
        context=payload.context,
    )
    return {"status": "ok"}
