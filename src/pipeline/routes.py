from fastapi import APIRouter, Depends
from psycopg import Connection

from ..auth.dependencies import get_db
from .transaction_parser_to_table import run_staging_to_transactions

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.post("/transactions/load-from-staging")
def post_load_transactions_from_staging(db: Connection = Depends(get_db)):
    """Run the staging → transactions pipeline (parse DONE rows, insert into `transactions`)."""
    return run_staging_to_transactions(db)
