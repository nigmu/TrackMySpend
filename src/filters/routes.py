from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from ..core.logging import get_logger
from ..db.connection import get_db
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
    logger.info("sender filter added pattern=%s", row["pattern"])
    return row


@router.delete("/{filter_id}")
def remove_filter(filter_id: int, conn: Connection = Depends(get_db)):
    if not db.delete_filter(conn, filter_id):
        raise HTTPException(status_code=404, detail="filter not found")
    logger.info("sender filter deleted id=%s", filter_id)
    return {"status": "deleted", "id": filter_id}
