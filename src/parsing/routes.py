from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from ..db.connection import get_db
from . import service

router = APIRouter(tags=["Parsing"])


@router.post("/parse")
def post_parse(db: Connection = Depends(get_db)):
    return service.parse_pending(db)


@router.get("/transactions")
def get_transactions(
    db: Connection = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items = service.list_transactions(db, limit=limit, offset=offset)
    return {
        "count": len(items),
        "total": service.count_transactions(db),
        "transactions": items,
    }
