"""
Gmail Banking Email Fetcher + Structured Parser
------------------------------------------------
Fetches a raw Gmail message and extracts a clean, structured
dict with every useful identifier — ready for the parser layer.

Dependencies:
    pip install google-api-python-client google-auth beautifulsoup4 lxml
"""

import base64
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from googleapiclient.discovery import build

from src.auth.credentials import build_gmail_credentials_for_email
from src.db.connection import connect

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
# MAIL VARIETY
CREDITCARD_OUT = "19d967e44f9bf1ec"
DEBITCARD_IN = "19d9548cb29ba500"
DEBITCARD_OUT = "19d95bfe09c239a9"

EMAIL_ADDRESS    = "nigamananda7161@gmail.com"
GMAIL_MESSAGE_ID = DEBITCARD_IN
OUTPUT_DIR       = Path(__file__).resolve().parent


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_header(headers: list[dict], name: str) -> str | None:
    """Case-insensitive header lookup. Returns first match or None."""
    name_lower = name.lower()
    for h in headers:
        if h["name"].lower() == name_lower:
            return h["value"]
    return None


def parse_x_unique_id(raw: str | None) -> dict:
    """
    HDFC embeds a JSON blob inside X-Unique-Id after the last '#'.
    Example value:
        A.177...#EMAIL@GMAIL.COM#{"divid":"UPIALRT","msgid":"..."}
    Returns the parsed dict, or {} if not present / not HDFC.
    """
    if not raw:
        return {}
    match = re.search(r'\{.*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def decode_body_data(data: str) -> str:
    """
    Gmail API returns body data as URL-safe base64 (no padding).
    Decode it to a UTF-8 string.
    """
    # Add padding if missing
    padded = data + "=" * (4 - len(data) % 4)
    raw_bytes = base64.urlsafe_b64decode(padded)
    return raw_bytes.decode("utf-8", errors="replace")


def extract_clean_text_from_html(html: str) -> str:
    """
    Parse the bank's HTML email and return only the meaningful
    plain-text content — stripping layout tags, images, scripts,
    tracking pixels and collapsing all whitespace.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove noise elements
    for tag in soup(["script", "style", "img", "a", "head"]):
        tag.decompose()

    text = soup.get_text(separator=" ")

    # Collapse all whitespace (tabs, newlines, multiple spaces)
    text = re.sub(r'\s+', ' ', text).strip()

    # Remove the boilerplate HDFC footer phrases if present
    boilerplate_patterns = [
        r'For more details on Service charges and Fees.*$',
        r'© HDFC Bank.*$',
        r'Warm Regards,\s*HDFC Bank.*$',
        r'If you did not authorize.*?7308080808\.',
    ]
    for pattern in boilerplate_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL).strip()

    return text


def find_html_part(payload: dict) -> str | None:
    """
    Recursively walk MIME parts to find text/html body data.
    Handles simple and nested multipart structures.
    """
    mime = payload.get("mimeType", "")

    if mime == "text/html":
        data = payload.get("body", {}).get("data")
        return decode_body_data(data) if data else None

    if mime == "text/plain":
        # Prefer plain text if it exists (rare for HDFC, useful for others)
        data = payload.get("body", {}).get("data")
        return decode_body_data(data) if data else None

    # Recurse into parts
    for part in payload.get("parts", []):
        result = find_html_part(part)
        if result:
            return result

    return None


def determine_bank(from_header: str | None, ses_header: str | None) -> str:
    """Identify the sending bank from known email domains and SES tags."""
    BANK_DOMAIN_MAP = {
        "hdfcbank.bank.in":  "HDFC",
        "hdfcbank.net":      "HDFC",
        "icicibank.com":     "ICICI",
        "sbi.co.in":         "SBI",
        "axisbank.com":      "Axis",
        "kotak.com":         "Kotak",
        "yesbank.in":        "Yes Bank",
        "indusind.com":      "IndusInd",
    }
    SES_TAG_MAP = {
        "hdfc-c": "HDFC",
        "icici-c": "ICICI",
    }

    if from_header:
        for domain, bank in BANK_DOMAIN_MAP.items():
            if domain in from_header.lower():
                return bank

    if ses_header:
        for tag, bank in SES_TAG_MAP.items():
            if tag in ses_header.lower():
                return bank

    return "UNKNOWN"


def map_divid_to_email_type(divid: str | None) -> str:
    """
    Map HDFC's internal divid codes to human-readable email types.
    Extend this as you discover more codes.
    """
    DIVID_MAP = {
        "UPIALRT":  "upi_alert",
        "DCALRT":   "debit_card_alert",
        "CCALRT":   "credit_card_alert",
        "EMIDUE":   "emi_due",
        "SIPCONF":  "sip_confirmation",
        "NACHDBT":  "nach_auto_debit",
        "NEFTALRT": "neft_alert",
        "IMPSALRT": "imps_alert",
        "STMTALRT": "statement_alert",
        "ODLMT":    "od_limit_alert",
    }
    return DIVID_MAP.get(divid, "unknown") if divid else "unknown"


# ─────────────────────────────────────────────
# MAIN STRUCTURED EXTRACTOR
# ─────────────────────────────────────────────

def extract_structured_email(raw_msg: dict) -> dict:
    """
    Takes a raw Gmail API message (format=full) and returns a
    clean structured dict with all useful identifiers extracted.
    """
    headers     = raw_msg["payload"]["headers"]
    from_val    = get_header(headers, "From")
    ses_tag     = get_header(headers, "X-Ses-Configuration-Set")
    x_unique    = get_header(headers, "X-Unique-Id")
    date_str    = get_header(headers, "Date")
    subject     = get_header(headers, "Subject")
    dkim_domain = None

    # Extract DKIM domain (first DKIM-Signature's d= field)
    for h in headers:
        if h["name"] == "DKIM-Signature":
            m = re.search(r'\bd=([^;]+)', h["value"])
            if m:
                dkim_domain = m.group(1).strip()
                break

    # Parse date header to ISO8601
    date_iso = None
    if date_str:
        try:
            dt = parsedate_to_datetime(date_str)
            date_iso = dt.isoformat()
        except Exception:
            date_iso = date_str

    # Internal date (ms epoch → UTC ISO)
    internal_ms   = int(raw_msg.get("internalDate", 0))
    received_utc  = datetime.fromtimestamp(internal_ms / 1000, tz=timezone.utc).isoformat()

    # X-Unique-Id parsing (HDFC specific)
    unique_id_meta = parse_x_unique_id(x_unique)
    divid          = unique_id_meta.get("divid")
    hdfc_msg_id    = unique_id_meta.get("msgid")

    # Bank identification
    bank = determine_bank(from_val, ses_tag)

    # Email type from divid (HDFC) or subject keyword fallback
    email_type = map_divid_to_email_type(divid)
    if email_type == "unknown" and subject:
        subj_lower = subject.lower()
        if "upi"     in subj_lower: email_type = "upi_alert"
        elif "debit" in subj_lower: email_type = "debit_alert"
        elif "credit"in subj_lower: email_type = "credit_alert"
        elif "emi"   in subj_lower: email_type = "emi_due"
        elif "sip"   in subj_lower: email_type = "sip_confirmation"

    # Extract and clean body
    raw_html   = find_html_part(raw_msg["payload"])
    clean_body = extract_clean_text_from_html(raw_html) if raw_html else None

    # Authentication signals
    arc_auth = get_header(headers, "ARC-Authentication-Results") or ""
    auth_signals = {
        "dkim_pass": "dkim=pass" in arc_auth,
        "spf_pass":  "spf=pass"  in arc_auth,
        "dmarc_pass":"dmarc=pass" in arc_auth,
        "dmarc_policy": "p=REJECT" if "p=REJECT" in arc_auth else
                        "p=QUARANTINE" if "p=QUARANTINE" in arc_auth else "unknown",
    }

    return {
        # ── Identity ──────────────────────────────
        "gmail_message_id":         raw_msg["id"],
        "thread_id":                raw_msg["threadId"],
        "history_id":               raw_msg.get("historyId"),
        "label_ids":                raw_msg.get("labelIds", []),
        "size_estimate_bytes":      raw_msg.get("sizeEstimate"),

        # ── Timestamps ────────────────────────────
        "date_sent_iso":            date_iso,
        "received_at_utc":          received_utc,
        "internal_date_ms":         internal_ms,

        # ── Routing ───────────────────────────────
        "from":                     from_val,
        "to":                       get_header(headers, "To"),
        "delivered_to":             get_header(headers, "Delivered-To"),
        "subject":                  subject,
        "message_id_header":        get_header(headers, "Message-ID"),
        "return_path":              get_header(headers, "Return-Path"),

        # ── Bank & Type Classification ────────────
        "bank":                     bank,
        "email_type":               email_type,
        "dkim_domain":              dkim_domain,
        "ses_config_set":           ses_tag,

        # ── HDFC-Specific Metadata ─────────────────
        "hdfc_divid":               divid,        # e.g. "UPIALRT"
        "hdfc_msg_id":              hdfc_msg_id,  # HDFC's own message ID
        "x_unique_id_raw":          x_unique,

        # ── Auth Signals (trust check) ─────────────
        "auth":                     auth_signals,

        # ── Content ───────────────────────────────
        "snippet":                  raw_msg.get("snippet"),
        "clean_body_text":          clean_body,   # ← feed this to the parser

        # ── MIME Info ─────────────────────────────
        "mime_type":                raw_msg["payload"].get("mimeType"),
        "has_plain_text_part":      any(
                                        p.get("mimeType") == "text/plain"
                                        for p in raw_msg["payload"].get("parts", [])
                                    ),
    }


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

def main() -> None:
    db = connect()
    try:
        creds = build_gmail_credentials_for_email(db, EMAIL_ADDRESS)
    finally:
        db.close()
    service = build("gmail", "v1", credentials=creds)

    # Fetch raw message (format=full gives us headers + body parts)
    raw_msg = service.users().messages().get(
        userId="me",
        id=GMAIL_MESSAGE_ID,
        format="full",
    ).execute()

    # Save raw for debugging
    raw_path = OUTPUT_DIR / "RAW_JSON.json"
    raw_path.write_text(
        json.dumps(raw_msg, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Raw saved  → {raw_path}")

    # Extract structured data
    structured = extract_structured_email(raw_msg)

    # Save structured output
    out_path = OUTPUT_DIR / "STRUCTURED_EMAIL.json"
    out_path.write_text(
        json.dumps(structured, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Structured → {out_path}")
    print()
    print("── Snapshot ──────────────────────────────────")
    print(f"  Bank        : {structured['bank']}")
    print(f"  Email Type  : {structured['email_type']}")
    print(f"  HDFC divid  : {structured['hdfc_divid']}")
    print(f"  Date Sent   : {structured['date_sent_iso']}")
    print(f"  Auth        : {structured['auth']}")
    print(f"  Body Text   : {(structured.get('clean_body_text') or '')[:2000]}.")
    print("───────────────────────────────────────────────")


if __name__ == "__main__":
    main()