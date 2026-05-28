"""HTTP routes for the pipeline module.

All non-auth pipeline endpoints live here. Pure parsers are in `src.parsing`
and never expose HTTP.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection
from pydantic import BaseModel

from ..db.dependencies import get_db
from .keywords import add_sender_keyword, get_sender_keywords
from . import db as pipeline_db
from .stage1_to_stage2 import run_sender_filter
from .stage2_to_transactions import run_staging_to_transactions

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


class AddKeywordRequest(BaseModel):
    keyword: str


@router.get("/keywords")
def get_keywords(db: Connection = Depends(get_db)):
    keywords = get_sender_keywords(db)
    return {"count": len(keywords), "keywords": keywords}


@router.post("/keywords")
def add_keyword(payload: AddKeywordRequest, db: Connection = Depends(get_db)):
    try:
        keywords = add_sender_keyword(db, payload.keyword)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(keywords), "keywords": keywords}


@router.post("/stage1-to-stage2/run")
def post_run_stage1_to_stage2(
    db: Connection = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=1000),
):
    return run_sender_filter(db, limit=limit)


@router.get("/transactions")
def get_transactions(
    db: Connection = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items = pipeline_db.list_transactions(db, limit=limit, offset=offset)
    total = pipeline_db.count_transactions(db)
    return {"count": len(items), "total": total, "transactions": items}


@router.post("/transactions/load-from-staging")
def post_load_transactions_from_staging(db: Connection = Depends(get_db)):
    """Run the stage 2 -> transactions pipeline (atomic per run)."""
    return run_staging_to_transactions(db)
