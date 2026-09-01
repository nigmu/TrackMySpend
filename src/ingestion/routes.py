from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from ..db.connection import get_db
from . import db, service

router = APIRouter(tags=["Ingestion"])


@router.post("/sync")
def post_sync_all(conn: Connection = Depends(get_db)):
    return service.run_sync_all(conn, trigger="manual")


@router.post("/sync/{account_id}")
def post_sync_one(account_id: int, conn: Connection = Depends(get_db)):
    result = service.run_sync_account(conn, account_id, trigger="manual")
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="account not found")
    if result.get("status") == "inactive":
        raise HTTPException(status_code=400, detail="account is inactive")
    return result


@router.get("/mails")
def get_mails(
    conn: Connection = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items = db.list_mails(conn, limit=limit, offset=offset)
    return {"count": len(items), "total": db.count_mails(conn), "mails": items}
