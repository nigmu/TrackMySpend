from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from ..core.logging import get_logger
from ..db.connection import get_db
from ..logs.db import insert_event_log
from . import db

logger = get_logger(__name__)
router = APIRouter(prefix="/filters", tags=["Filters"])


class AddFilterRequest(BaseModel):
    pattern: str


@router.get("")
def get_filters(conn: Connection = Depends(get_db)):
    items = db.list_filters(conn)
    return {"count": len(items), "filters": items}


@router.post("")
def post_filter(payload: AddFilterRequest, conn: Connection = Depends(get_db)):
    try:
        row = db.add_filter(conn, payload.pattern)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("sender filter added id=%s pattern=%s", row["id"], row["pattern"])
    insert_event_log(
        "filter.added",
        "filters",
        f"Sender filter added id={row['id']} pattern={row['pattern']}",
        context={"id": row["id"], "pattern": row["pattern"]},
    )
    return row


@router.delete("/{filter_id}")
def remove_filter(filter_id: int, conn: Connection = Depends(get_db)):
    pattern = db.delete_filter(conn, filter_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="filter not found")
    logger.info("sender filter deleted id=%s pattern=%s", filter_id, pattern)
    insert_event_log(
        "filter.deleted",
        "filters",
        f"Sender filter deleted id={filter_id} pattern={pattern}",
        context={"id": filter_id, "pattern": pattern},
    )
    return {"status": "deleted", "id": filter_id}
