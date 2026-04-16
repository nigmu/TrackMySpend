import sqlite3
import time
from datetime import datetime, timezone
from src.ingestion.email_fetcher import (
    fetch_latest_filtered_messages_for_one_account,
)
from src.ingestion.staging_store import store_for_parser
from ..global_configs import DB_PATH


def _mark_account_polled(conn: sqlite3.Connection, account_id: int) -> None:
    conn.execute(
        "UPDATE email_accounts SET last_polled_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), account_id),
    )
    conn.commit()


def _update_history_id(conn, account_id, history_id):
    if history_id:
        conn.execute(
            "UPDATE email_accounts SET last_history_id = ? WHERE id = ?",
            (history_id, account_id),
        )
        conn.commit()


def _is_due_to_poll(last_polled_at: str | None, polling_interval_min: int, now: datetime | None = None) -> bool:
    """
    Return True when account should be polled according to its configured interval.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if not last_polled_at:
        return True
    last = datetime.fromisoformat(last_polled_at)
    age_sec = (now - last).total_seconds()
    return age_sec >= int(polling_interval_min) * 60


def _load_active_accounts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, email_address, polling_interval_min, last_polled_at
        FROM email_accounts
        WHERE is_active = 1
        """
    ).fetchall()


def sync_latest_filtered_messages_for_one_account(account_id: int, keep_existing_staging: bool = True) -> dict:
    """
    Run one incremental historyId-based sync for a single account and
    persist sync markers.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, email_address, is_active
            FROM email_accounts
            WHERE id = ?
            """,
            (account_id,),
        ).fetchone()
        if not row:
            return {"account_id": account_id, "messages": [], "new_history_id": None, "status": "not_found"}
        if int(row["is_active"]) != 1:
            return {"account_id": account_id, "messages": [], "new_history_id": None, "status": "inactive"}

        messages, new_history_id = fetch_latest_filtered_messages_for_one_account(account_id)
        staged_for_parser = store_for_parser(messages, keep_existing=keep_existing_staging)
        _update_history_id(conn, account_id, new_history_id)
        _mark_account_polled(conn, account_id)
        return {
            "account_id": account_id,
            "email_address": row["email_address"],
            "messages": messages,
            "count": len(messages),
            "staged_for_parser": staged_for_parser,
            "new_history_id": new_history_id,
            "status": "ok",
        }
    finally:
        conn.close()


def sync_latest_filtered_messages_for_all_accounts(keep_existing_staging: bool = True) -> dict:
    """
    Run one incremental sync for every active account and return detailed per-account results.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = _load_active_accounts(conn)
    finally:
        conn.close()

    results = []
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
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            now = datetime.now(timezone.utc)
            due_rows = [
                row
                for row in _load_active_accounts(conn)
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
        time.sleep(30)  # coarse loop tick