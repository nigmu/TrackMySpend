from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..accounts.service import credentials_from_account
from ..core.config import BOOTSTRAP_MESSAGE_COUNT
from ..core.logging import get_logger

logger = get_logger(__name__)


class HistoryStale(Exception):
    pass


def gmail_service(account: dict):
    creds = credentials_from_account(account)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def profile_history_id(service) -> int:
    return int(service.users().getProfile(userId="me").execute()["historyId"])


def gmail_search_query(patterns: list[str]) -> str:
    return " OR ".join(f"from:{p}" for p in patterns)


def list_bootstrap_ids(service, query: str, n: int = BOOTSTRAP_MESSAGE_COUNT) -> list[str]:
    resp = service.users().messages().list(
        userId="me", q=query, maxResults=n
    ).execute()
    return [m["id"] for m in resp.get("messages", [])]


def get_message_meta(service, msg_id: str) -> dict:
    msg = service.users().messages().get(
        userId="me",
        id=msg_id,
        format="metadata",
        metadataHeaders=["From", "Subject", "Date"],
    ).execute()
    headers = {
        h["name"].lower(): h["value"]
        for h in msg.get("payload", {}).get("headers", [])
        if h.get("name")
    }
    return {
        "gmail_message_id": msg["id"],
        "gmail_thread_id": msg.get("threadId"),
        "sender": headers.get("from"),
        "subject": headers.get("subject"),
        "snippet": msg.get("snippet"),
        "email_sent_at": _parse_header_date(headers.get("date")),
        "gmail_received_at": _internal_ms_to_dt(msg.get("internalDate")),
    }


def list_history_message_ids(service, start_history_id: int) -> tuple[list[str], int]:
    ids: list[str] = []
    page_token = None
    latest = start_history_id
    while True:
        kwargs = {
            "userId": "me",
            "startHistoryId": start_history_id,
            "historyTypes": ["messageAdded"],
            "maxResults": 500,
        }
        if page_token:
            kwargs["pageToken"] = page_token
        try:
            resp = service.users().history().list(**kwargs).execute()
        except HttpError as exc:
            if exc.resp.status == 404:
                raise HistoryStale from exc
            raise
        latest = int(resp.get("historyId", latest))
        for event in resp.get("history", []):
            for added in event.get("messagesAdded", []):
                mid = (added.get("message") or {}).get("id")
                if mid:
                    ids.append(mid)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    seen: set[str] = set()
    unique: list[str] = []
    for mid in ids:
        if mid not in seen:
            seen.add(mid)
            unique.append(mid)
    return unique, latest


def _parse_header_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _internal_ms_to_dt(ms: str | int | None) -> datetime | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except Exception:
        return None
