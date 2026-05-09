"""Ingestion service: orchestrates Gmail fetch + sync.

This layer decides *when* to fetch and *what* to do with the result. It
contains no SQL: persistence is delegated to `auth.db` (for
`user_email_accounts` markers) and `pipeline.db` (for staging inserts via the stage-0 helper).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from psycopg import Connection

from ..auth.db import (
    get_account_sync_state,
    list_active_accounts,
    update_last_history_id,
    update_last_polled_at,
)
from ..db.connection import connect
from ..pipeline.stage0_ingest_to_stage1 import store_messages_in_stage1
from .gmail_client import fetch_latest_filtered_messages_for_one_account


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_due_to_poll(
    last_polled_at: str | datetime | None,
    polling_interval_min: int,
    now: datetime | None = None,
) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)
    if not last_polled_at:
        return True
    if isinstance(last_polled_at, datetime):
        last = last_polled_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    else:
        last = datetime.fromisoformat(last_polled_at)
    age_sec = (now - last).total_seconds()
    return age_sec >= int(polling_interval_min) * 60


def sync_latest_filtered_messages_for_one_account(
    account_id: int,
    keep_existing_staging: bool = True,
) -> dict:
    """Run one incremental historyId-based sync for a single account."""
    conn = connect()
    try:
        account = get_account_sync_state(conn, account_id)
        if not account:
            return {"account_id": account_id, "messages": [], "new_history_id": None, "status": "not_found"}
        if not account["is_active"]:
            return {"account_id": account_id, "messages": [], "new_history_id": None, "status": "inactive"}

        messages, new_history_id = fetch_latest_filtered_messages_for_one_account(account_id)
        staged_for_parser = store_messages_in_stage1(
            conn, messages, keep_existing=keep_existing_staging
        )
        update_last_history_id(conn, account_id, new_history_id)
        update_last_polled_at(conn, account_id, _now_iso())
        conn.commit()

        return {
            "account_id": account_id,
            "email_address": account["email_address"],
            "messages": messages,
            "count": len(messages),
            "staged_for_parser": staged_for_parser,
            "new_history_id": new_history_id,
            "status": "ok",
        }
    finally:
        conn.close()


def sync_latest_filtered_messages_for_all_accounts(keep_existing_staging: bool = True) -> dict:
    """Run one incremental sync for every active account."""
    conn = connect()
    try:
        rows = list_active_accounts(conn)
    finally:
        conn.close()

    results: list[dict] = []
    total_messages = 0
    for row in rows:
        result = sync_latest_filtered_messages_for_one_account(
            account_id=row["id"],
            keep_existing_staging=keep_existing_staging,
        )
        results.append(result)
        if result.get("status") == "ok":
            total_messages += int(result.get("count", 0))

    return {
        "accounts_processed": len(results),
        "total_messages": total_messages,
        "results": results,
    }


def run_poller_loop() -> None:
    while True:
        conn = connect()
        try:
            now = datetime.now(timezone.utc)
            due_rows = [
                row
                for row in list_active_accounts(conn)
                if _is_due_to_poll(
                    last_polled_at=row["last_polled_at"],
                    polling_interval_min=row["polling_interval_min"],
                    now=now,
                )
            ]
        finally:
            conn.close()

        for row in due_rows:
            result = sync_latest_filtered_messages_for_one_account(account_id=row["id"])
            if result.get("status") == "ok":
                print(f"[poller] {result['email_address']} fetched={result['count']}")
        time.sleep(30)
