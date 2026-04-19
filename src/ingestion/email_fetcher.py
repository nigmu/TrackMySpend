import base64
import re
from datetime import datetime, timezone
from html import unescape
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.auth.config import GMAIL_SCOPES, get_oauth_config
from src.security.crypto import decrypt_text

from ..db_connection import connect

def _build_creds(access_token_enc: str, refresh_token_enc: str) -> Credentials:
    oauth = get_oauth_config()["web"]
    return Credentials(
        token=decrypt_text(access_token_enc),
        refresh_token=decrypt_text(refresh_token_enc),
        token_uri=oauth["token_uri"],
        client_id=oauth["client_id"],
        client_secret=oauth["client_secret"],
        scopes=GMAIL_SCOPES,
    )


def _get_header_map(payload: dict) -> dict[str, str]:
    return {
        h.get("name", ""): h.get("value", "")
        for h in payload.get("headers", [])
        if h.get("name")
    }


def _internal_date_ms_to_iso_utc(internal_date_ms: str | None) -> str | None:
    if not internal_date_ms:
        return None
    try:
        dt = datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def _parse_header_date_to_iso(date_header: str | None) -> str | None:
    if not date_header:
        return None
    try:
        dt = parsedate_to_datetime(date_header)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def _decode_base64url_to_text(data: str | None) -> str | None:
    if not data:
        return None
    try:
        padded = data + "=" * (-len(data) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


def _strip_html_to_text(html: str) -> str:
    # Remove script/style contents first.
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    # Strip remaining tags.
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    text = unescape(text)
    # Normalize whitespace.
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def _extract_text_from_payload(payload: dict | None, *, max_chars: int = 50000) -> str:
    """
    Extract a human-readable full body:
    - Prefer `text/plain` parts.
    - Fallback to `text/html` parts (strip tags).
    """
    if not payload:
        return ""

    mime_type = (payload.get("mimeType") or "").lower()
    body_data = (payload.get("body") or {}).get("data")
    if mime_type.startswith("text/plain"):
        decoded = _decode_base64url_to_text(body_data)
        if decoded:
            decoded = re.sub(r"\\s+", " ", decoded).strip()
            return decoded[:max_chars]

    # Search subparts first (often the real body is nested).
    for part in payload.get("parts", []) or []:
        extracted = _extract_text_from_payload(part, max_chars=max_chars)
        if extracted:
            return extracted

    # If nothing found in parts, try html body at this level.
    if mime_type.startswith("text/html"):
        html = _decode_base64url_to_text(body_data)
        if html:
            return _strip_html_to_text(html)[:max_chars]

    # Last resort: if there's body data but no mime type we understand.
    if body_data:
        decoded = _decode_base64url_to_text(body_data)
        if decoded:
            decoded = re.sub(r"\\s+", " ", decoded).strip()
            return decoded[:max_chars]

    return ""


def fetch_top_n_raw_messages_for_one_account(account_id: int, top_n: int = 10) -> list[dict]:
    """
    Fetch top N raw message payloads (metadata + snippet + payload) for an account.
    This function only fetches data; it does not update polling metadata in DB.
    """
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT id, email_address, oauth_access_token, oauth_refresh_token, is_active
            FROM email_accounts
            WHERE id = %s
            """,
            (account_id,),
        ).fetchone()
        if not row:
            return []
        if not row["is_active"]:
            return []

        creds = _build_creds(row["oauth_access_token"], row["oauth_refresh_token"])
        gmail = build("gmail", "v1", credentials=creds)

        resp = gmail.users().messages().list(
            userId="me",
            maxResults=top_n,
            q="in:inbox",
        ).execute()

        out = []
        for m in resp.get("messages", []):
            full = gmail.users().messages().get(
                userId="me",
                id=m["id"],
                format="full",
            ).execute()
            out.append(
                {
                    "account_id": row["id"],
                    "email_address": row["email_address"],
                    "gmail_message_id": full["id"],
                    "thread_id": full.get("threadId"),
                    "internal_date": full.get("internalDate"),
                    "snippet": full.get("snippet", ""),
                    # "full_body_text": _extract_text_from_payload(full.get("payload", {})),
                    "payload": full.get("payload", {}),
                }
            )

        return out
    finally:
        conn.close()


def fetch_top_n_filtered_messages_for_one_account(account_id: int, top_n: int = 10) -> list[dict]:
    """
    Fetch top N messages with essential fields only.
    Includes From, Subject, Date, snippet, internal date, and parsed timestamps.
    """
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT id, email_address, oauth_access_token, oauth_refresh_token, is_active
            FROM email_accounts
            WHERE id = %s
            """,
            (account_id,),
        ).fetchone()
        if not row or not row["is_active"]:
            return []

        creds = _build_creds(row["oauth_access_token"], row["oauth_refresh_token"])
        gmail = build("gmail", "v1", credentials=creds)

        resp = gmail.users().messages().list(
            userId="me",
            maxResults=top_n,
            q="in:inbox",
        ).execute()

        out = []
        for m in resp.get("messages", []):
            full = gmail.users().messages().get(
                userId="me",
                id=m["id"],
                format="full",
            ).execute()

            headers = _get_header_map(full.get("payload", {}))
            raw_date = headers.get("Date")
            internal_date_ms = full.get("internalDate")
            out.append(
                {
                    "account_id": row["id"],
                    "email_address": row["email_address"],
                    "gmail_message_id": full.get("id"),
                    "thread_id": full.get("threadId"),
                    "from": headers.get("From"),
                    "to": headers.get("To"),
                    "subject": headers.get("Subject"),
                    "date_header": raw_date,
                    "internal_date_ms": internal_date_ms,
                    "gmail_received_at_utc": _internal_date_ms_to_iso_utc(internal_date_ms),
                    "date_header_iso": _parse_header_date_to_iso(raw_date),
                    "snippet": full.get("snippet", ""),
                    # "full_body_text": _extract_text_from_payload(full.get("payload", {})),
                }
            )

        return out
    finally:
        conn.close()


def fetch_top_n_filtered_messages_for_all_accounts(top_n: int = 10) -> list[dict]:
    """
    Fetch top N filtered messages for every active account.
    Returns one grouped result entry per account.
    """
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT id, email_address
            FROM email_accounts
            WHERE is_active = TRUE
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        conn.close()

    results: list[dict] = []
    for row in rows:
        messages = fetch_top_n_filtered_messages_for_one_account(account_id=row["id"], top_n=top_n)
        results.append(
            {
                "account_id": row["id"],
                "email_address": row["email_address"],
                "count": len(messages),
                "messages": messages,
            }
        )
    return results


def fetch_latest_filtered_messages_for_one_account(account_id: int) -> tuple[list[dict], str | None]:
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT id, email_address, oauth_access_token, oauth_refresh_token,
                   is_active, last_history_id
            FROM email_accounts
            WHERE id = %s
            """,
            (account_id,),
        ).fetchone()

        if not row or not row["is_active"]:
            return [], None

        creds = _build_creds(row["oauth_access_token"], row["oauth_refresh_token"])
        gmail = build("gmail", "v1", credentials=creds)

        last_history_id = row["last_history_id"]

        # FIRST RUN (bootstrap)
        if not last_history_id:
            resp = gmail.users().messages().list(
                userId="me",
                maxResults=5,
                q="in:inbox",
            ).execute()

            msgs = resp.get("messages", [])
            if not msgs:
                return [], None

            full = gmail.users().messages().get(
                userId="me",
                id=msgs[0]["id"],
                format="full",
            ).execute()

            return [], full.get("historyId")

        # INCREMENTAL
        resp = gmail.users().history().list(
            userId="me",
            startHistoryId=last_history_id,
        ).execute()

        new_ids = []
        for h in resp.get("history", []):
            for m in h.get("messagesAdded", []):
                new_ids.append(m["message"]["id"])

        out = []
        for msg_id in new_ids:
            try:
                full = gmail.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full",
                ).execute()
            except HttpError as exc:
                # Messages referenced in history can be deleted/moved before fetch.
                # Skip missing messages so one stale id doesn't fail the full sync.
                if getattr(exc, "resp", None) is not None and exc.resp.status == 404:
                    continue
                raise

            headers = _get_header_map(full.get("payload", {}))
            raw_date = headers.get("Date")
            internal_date_ms = full.get("internalDate")
            out.append(
                {
                    "account_id": row["id"],
                    "email_address": row["email_address"],
                    "gmail_message_id": full.get("id"),
                    "thread_id": full.get("threadId"),
                    "from": headers.get("From"),
                    "to": headers.get("To"),
                    "subject": headers.get("Subject"),
                    "date_header": raw_date,
                    "internal_date_ms": internal_date_ms,
                    "gmail_received_at_utc": _internal_date_ms_to_iso_utc(internal_date_ms),
                    "date_header_iso": _parse_header_date_to_iso(raw_date),
                    "snippet": full.get("snippet", ""),
                    # "full_body_text": _extract_text_from_payload(full.get("payload", {})),
                    "payload": full.get("payload", {}),
                }
            )

        return out, resp.get("historyId")

    finally:
        conn.close()


