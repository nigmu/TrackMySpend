from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from ..db.connection import get_db
from . import db

router = APIRouter(tags=["Logs"])


@router.get("/logs")
def get_logs(
    conn: Connection = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items = db.list_event_logs(conn, limit=limit, offset=offset)
    return {"count": len(items), "total": db.count_event_logs(conn), "logs": items}
