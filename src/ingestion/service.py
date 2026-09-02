from psycopg import Connection

from ..accounts import db as accounts_db
from ..core.config import BOOTSTRAP_MESSAGE_COUNT
from ..core.logging import get_logger
from ..filters.db import active_patterns
from ..logs.db import insert_event_log
from ..parsing.service import parse_pending
from . import db
from .gmail_client import (
    HistoryStale,
    get_message_meta,
    gmail_search_query,
    gmail_service,
    list_bootstrap_ids,
    list_history_message_ids,
    profile_history_id,
)

logger = get_logger(__name__)


def match_sender(sender: str | None, patterns: list[str]) -> str | None:
    haystack = (sender or "").lower()
    for pattern in patterns:
        if pattern.lower() in haystack:
            return pattern
    return None


def _ingest_ids(conn: Connection, service, account_id: int, ids: list[str], patterns: list[str]) -> dict:
    seen = inserted = skipped = failed = 0
    for msg_id in ids:
        seen += 1
        try:
            msg = get_message_meta(service, msg_id)
        except Exception:
            logger.warning("message fetch failed id=%s", msg_id, exc_info=True)
            failed += 1
            continue
        rule = match_sender(msg.get("sender"), patterns)
        if not rule:
            skipped += 1
            continue
        if db.insert_mail(conn, account_id, msg, rule):
            inserted += 1
        else:
            skipped += 1
    return {"seen": seen, "inserted": inserted, "skipped": skipped, "failed": failed}


def _bootstrap(conn: Connection, service, account_id: int, patterns: list[str]) -> tuple[dict, int]:
    query = gmail_search_query(patterns)
    ids = list_bootstrap_ids(service, query, BOOTSTRAP_MESSAGE_COUNT)
    stats = _ingest_ids(conn, service, account_id, ids, patterns)
    history_id = profile_history_id(service)
    logger.info(
        "bootstrap account_id=%s seen=%s inserted=%s skipped=%s",
        account_id, stats["seen"], stats["inserted"], stats["skipped"],
    )
    return stats, history_id


def sync_one(conn: Connection, account: dict, trigger: str) -> dict:
    account_id = account["id"]
    run_id = db.start_sync_run(conn, account_id, trigger)
    insert_event_log(
        "gmail.sync_started",
        "ingestion",
        f"Gmail sync started account_id={account_id} trigger={trigger}",
        context={"account_id": account_id, "trigger": trigger, "run_id": run_id},
    )
    patterns = active_patterns(conn)
    if not patterns:
        db.finish_sync_run(conn, run_id, "done", error_message="no sender filters")
        logger.info("sync skipped account_id=%s reason=no_filters", account_id)
        insert_event_log(
            "gmail.sync_completed",
            "ingestion",
            f"Gmail sync skipped account_id={account_id} reason=no_filters",
            context={"account_id": account_id, "trigger": trigger},
        )
        return {"account_id": account_id, "status": "no_filters"}

    try:
        service = gmail_service(account)
        if account.get("last_history_id"):
            try:
                ids, new_history_id = list_history_message_ids(service, int(account["last_history_id"]))
                stats = _ingest_ids(conn, service, account_id, ids, patterns)
            except HistoryStale:
                logger.warning("historyId stale account_id=%s, falling back to bootstrap", account_id)
                stats, new_history_id = _bootstrap(conn, service, account_id, patterns)
        else:
            stats, new_history_id = _bootstrap(conn, service, account_id, patterns)

        accounts_db.update_sync_state(conn, account_id, new_history_id)
        db.finish_sync_run(
            conn, run_id, "done",
            seen=stats["seen"], inserted=stats["inserted"],
            skipped=stats["skipped"], failed=stats["failed"],
        )
        logger.info(
            "sync done account_id=%s trigger=%s seen=%s inserted=%s skipped=%s failed=%s",
            account_id, trigger, stats["seen"], stats["inserted"], stats["skipped"], stats["failed"],
        )
        insert_event_log(
            "gmail.sync_completed",
            "ingestion",
            f"Gmail sync done account_id={account_id}",
            context={"account_id": account_id, "trigger": trigger, **stats},
        )
        return {"account_id": account_id, "status": "done", **stats}
    except Exception as exc:
        db.finish_sync_run(conn, run_id, "failed", error_message=str(exc))
        logger.exception("sync failed account_id=%s", account_id)
        insert_event_log(
            "gmail.sync_failed",
            "ingestion",
            f"Gmail sync failed account_id={account_id}",
            severity="error",
            context={"account_id": account_id, "trigger": trigger, "error": str(exc)},
        )
        return {"account_id": account_id, "status": "failed", "error": str(exc)}


def run_sync_all(conn: Connection, trigger: str) -> dict:
    accounts = accounts_db.list_active_accounts(conn)
    results = [sync_one(conn, acc, trigger) for acc in accounts]
    parse_result = parse_pending(conn)
    return {"accounts": results, "parse": parse_result}


def run_sync_account(conn: Connection, account_id: int, trigger: str) -> dict:
    account = accounts_db.get_account(conn, account_id)
    if not account:
        return {"account_id": account_id, "status": "not_found"}
    if not account["is_active"]:
        return {"account_id": account_id, "status": "inactive"}
    result = sync_one(conn, account, trigger)
    result["parse"] = parse_pending(conn)
    return result


def run_due_accounts(conn: Connection) -> dict:
    due = accounts_db.list_due_accounts(conn)
    results = [sync_one(conn, acc, "poller") for acc in due]
    parse_result = parse_pending(conn) if due else {"claimed": 0, "done": 0, "failed": 0}
    if due:
        logger.info("poller ran accounts=%s", len(due))
    return {"accounts": results, "parse": parse_result}
