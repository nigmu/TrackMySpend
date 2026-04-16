from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .staging_store import (
    add_sender_keyword,
    get_sender_keywords,
    stage_sender_regex_matches,
)

router = APIRouter(prefix="/parsing", tags=["Parsing"])


class AddKeywordRequest(BaseModel):
    keyword: str


@router.get("/sender-keywords")
def get_parser_sender_keywords():
    return {"count": len(get_sender_keywords()), "keywords": get_sender_keywords()}


@router.post("/sender-keywords")
def add_parser_sender_keyword(payload: AddKeywordRequest):
    try:
        keywords = add_sender_keyword(payload.keyword)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(keywords), "keywords": keywords}


@router.post("/staging/sender-filter/run")
def run_sender_filter_staging(limit: int = Query(default=200, ge=1, le=1000)):
    return stage_sender_regex_matches(limit=limit)
