"""Rule-based parser for HDFC transaction emails.

Input is raw text (not structured JSON). The module first classifies the text
into a (type, instrument, channel) triple, then dispatches to the matching
parser function. Function names follow the convention:

    type_instrument_channel(text: str) -> dict

All parsers return a dict with the same shape (dates intentionally excluded):

    bank              -> issuing bank, e.g. "HDFC"
    type              -> credit / debit / reversal / auto payment / balance_update
    instrument        -> bank_account / credit_card
    channel           -> upi / debit_card / credit_card
    amount            -> float, transaction amount in INR (None if N/A)
    currency          -> "INR"
    account_last4     -> last 4 digits of the account or card involved
    counterparty      -> merchant / person / service name (None if N/A)
    counterparty_vpa  -> UPI VPA string if available, else None
    reference_number  -> UPI / transaction reference number if available, else None
    extras            -> dict with type-specific extras (e.g. frequency,
                         max_amount, balance, threshold)

Usage:
    parse_text(raw_email_text)          # single text -> dict
    parse_texts([text_a, text_b, ...])  # list of texts -> list of dicts
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

SAMPLE_JSON = Path(__file__).parent / "SAMPLE_MAILS" / "HDFC.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AMOUNT_RE = re.compile(r"Rs\.?\s*(?:INR\s*)?([\d,]+\.\d{2})", re.IGNORECASE)
_INR_RE = re.compile(r"INR\s*([\d,]+\.\d{2})", re.IGNORECASE)


def _to_float(num: str) -> float:
    return float(num.replace(",", ""))


def _first_amount(text: str) -> float | None:
    m = _AMOUNT_RE.search(text)
    if not m:
        m = _INR_RE.search(text)
    return _to_float(m.group(1)) if m else None


def _base_result(txn_type: str, instrument: str, channel: str) -> dict:
    return {
        "bank": "HDFC",
        "type": txn_type,
        "instrument": instrument,
        "channel": channel,
        "amount": None,
        "currency": "INR",
        "account_last4": None,
        "counterparty": None,
        "counterparty_vpa": None,
        "reference_number": None,
        "extras": {},
    }


# ---------------------------------------------------------------------------
# Classifier: raw text -> (type, instrument, channel)
# ---------------------------------------------------------------------------

def classify(text: str) -> tuple[str, str, str]:
    """Inspect raw email text and decide which parser should handle it.

    Raises ValueError if the text does not match any known pattern.
    """
    t = text.lower()

    # 1. Balance alert (before anything else; it has no 'debited'/'credited')
    if "dropped below" in t and "balance as of" in t:
        return ("balance_update", "bank_account", None)

    # 2. E-mandate / auto payment
    if "e-mandate" in t or "auto payment" in t:
        if "credit card" in t:
            return ("auto payment", "credit_card", "credit_card")
        if "debit card" in t:
            return ("auto payment", "bank_account", "debit_card")

    # 3. Reversal
    if "transaction reversal" in t or "reversal of rs" in t:
        if "credit card" in t:
            return ("reversal", "credit_card", "credit_card")

    # 4. Credit
    if "credited to your account" in t or "is successfully credited" in t:
        if "vpa" in t or "upi transaction reference" in t:
            return ("credit", "bank_account", "upi")

    # 5. Debit
    if "debited" in t:
        has_cc = "credit card" in t
        has_dc = "debit card" in t
        has_upi_ref = "upi transaction reference" in t
        has_vpa = "vpa" in t or re.search(r"\S+@\S+", text) is not None

        if has_cc and (has_upi_ref or (has_vpa and "towards" not in t)):
            return ("debit", "credit_card", "upi")
        if has_cc:
            return ("debit", "credit_card", "credit_card")
        if has_dc:
            return ("debit", "bank_account", "debit_card")
        if has_upi_ref or has_vpa:
            return ("debit", "bank_account", "upi")

    raise ValueError("Could not classify transaction text")


# ---------------------------------------------------------------------------
# Parser functions - one per type_instrument_channel combination
# ---------------------------------------------------------------------------

def credit_bank_account_upi(text: str) -> dict:
    """e.g. 'Rs. 240.00 is successfully credited to your account **2345 by VPA
    demouser997-1@okaxis DEMO USER ...'"""
    out = _base_result("credit", "bank_account", "upi")

    out["amount"] = _first_amount(text)

    m = re.search(r"account\s*\**\s*(\d{4})", text, re.IGNORECASE)
    if m:
        out["account_last4"] = m.group(1)

    m = re.search(
        r"by\s+VPA\s+(\S+@\S+?)\s+(.+?)\s+on\s+\d",
        text,
        re.IGNORECASE,
    )
    if m:
        out["counterparty_vpa"] = m.group(1)
        out["counterparty"] = m.group(2).strip()

    m = re.search(r"UPI transaction reference number is\s*(\d+)", text, re.IGNORECASE)
    if m:
        out["reference_number"] = m.group(1)

    return out


def reversal_credit_card_credit_card(text: str) -> dict:
    """e.g. 'Transaction reversal of Rs.14.35 ... Credit Card ending 4610.
    From Merchant:A UBER INDIA SYSTE PVT L ...'"""
    out = _base_result("reversal", "credit_card", "credit_card")

    out["amount"] = _first_amount(text)

    m = re.search(r"Credit Card ending\s*(\d{4})", text, re.IGNORECASE)
    if m:
        out["account_last4"] = m.group(1)

    m = re.search(r"From\s+Merchant\s*:\s*(.+?)\s+Date\s+Time", text, re.IGNORECASE)
    if m:
        out["counterparty"] = m.group(1).strip()

    return out


def debit_bank_account_upi(text: str) -> dict:
    """e.g. 'Rs.28.50 has been debited from account 2345 to VPA
    aamarkolkatametro.76509181@hdfcbank AAMAR KOLKATA METRO ...'"""
    out = _base_result("debit", "bank_account", "upi")

    out["amount"] = _first_amount(text)

    m = re.search(r"from\s+account\s*\**\s*(\d{4})", text, re.IGNORECASE)
    if m:
        out["account_last4"] = m.group(1)

    m = re.search(
        r"to\s+VPA\s+(\S+@\S+?)\s+(.+?)\s+on\s+\d",
        text,
        re.IGNORECASE,
    )
    if m:
        out["counterparty_vpa"] = m.group(1)
        out["counterparty"] = m.group(2).strip()

    m = re.search(r"UPI transaction reference number is\s*(\d+)", text, re.IGNORECASE)
    if m:
        out["reference_number"] = m.group(1)

    return out


def debit_bank_account_debit_card(text: str) -> dict:
    """e.g. 'Rs.120.00 is debited from your HDFC Bank Debit Card ending 4925
    at MORE on 26 Mar, 2026 at 18:18:21.'"""
    out = _base_result("debit", "bank_account", "debit_card")

    out["amount"] = _first_amount(text)

    m = re.search(r"Debit Card ending\s*(\d{4})", text, re.IGNORECASE)
    if m:
        out["account_last4"] = m.group(1)

    m = re.search(
        r"ending\s*\d{4}\s+at\s+(.+?)\s+on\s+\d{1,2}\s+[A-Za-z]{3}",
        text,
        re.IGNORECASE,
    )
    if m:
        out["counterparty"] = m.group(1).strip()

    return out


def debit_credit_card_upi(text: str) -> dict:
    """e.g. 'Rs.214.00 has been debited from your HDFC Bank RuPay Credit Card
    XX6517 to swiggystores@icici Swiggy on 29-03-26 ...'"""
    out = _base_result("debit", "credit_card", "upi")

    out["amount"] = _first_amount(text)

    m = re.search(r"Credit Card\s*(?:XX)?(\d{4})", text, re.IGNORECASE)
    if m:
        out["account_last4"] = m.group(1)

    m = re.search(
        r"(?:XX)?\d{4}\s+to\s+(\S+@\S+?)\s+(.+?)\s+on\s+\d",
        text,
        re.IGNORECASE,
    )
    if m:
        out["counterparty_vpa"] = m.group(1)
        out["counterparty"] = m.group(2).strip()

    m = re.search(r"UPI transaction reference number is\s*(\d+)", text, re.IGNORECASE)
    if m:
        out["reference_number"] = m.group(1)

    return out


def debit_credit_card_credit_card(text: str) -> dict:
    """e.g. 'Rs. 259.00 has been debited from your HDFC Bank Credit Card
    ending 6517 towards EATCLUB BRANDS PRIVATE on 18 Apr, 2026 ...'"""
    out = _base_result("debit", "credit_card", "credit_card")

    out["amount"] = _first_amount(text)

    m = re.search(r"Credit Card ending\s*(\d{4})", text, re.IGNORECASE)
    if m:
        out["account_last4"] = m.group(1)

    m = re.search(
        r"towards\s+(.+?)\s+on\s+\d{1,2}\s+[A-Za-z]{3}",
        text,
        re.IGNORECASE,
    )
    if m:
        out["counterparty"] = m.group(1).strip()

    return out


def auto_payment_credit_card_credit_card(text: str) -> dict:
    """e.g. 'Your payment for SPOTIFYINDIA is registered for E-mandate (Auto
    payment) using your HDFC Bank Credit Card ending 6517 ...'"""
    out = _base_result("auto payment", "credit_card", "credit_card")

    m = re.search(r"payment\s+for\s+(.+?)\s+is\s+registered", text, re.IGNORECASE)
    if m:
        out["counterparty"] = m.group(1).strip()

    m = re.search(r"Credit Card ending\s*(\d{4})", text, re.IGNORECASE)
    if m:
        out["account_last4"] = m.group(1)

    m = re.search(r"Current transaction amount\s*:\s*INR\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if m:
        out["amount"] = _to_float(m.group(1))

    m = re.search(r"Maximum transaction amount\s*:\s*INR\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if m:
        out["extras"]["max_amount"] = _to_float(m.group(1))

    m = re.search(r"Frequency\s*:\s*([^\n]+?)\s*(?:Start date|End date|$)", text, re.IGNORECASE)
    if m:
        out["extras"]["frequency"] = m.group(1).strip()

    m = re.search(r"SI Hub ID\s*:\s*(\S+)", text, re.IGNORECASE)
    if m:
        out["reference_number"] = m.group(1)

    return out


def auto_payment_bank_account_debit_card(text: str) -> dict:
    """e.g. 'Your payment for Google Cloud is registered for E-mandate (Auto
    payment) using your HDFC Bank Debit Card ending 4925 ...'"""
    out = _base_result("auto payment", "bank_account", "debit_card")

    m = re.search(r"payment\s+for\s+(.+?)\s+is\s+registered", text, re.IGNORECASE)
    if m:
        out["counterparty"] = m.group(1).strip()

    m = re.search(r"Debit Card ending\s*(\d{4})", text, re.IGNORECASE)
    if m:
        out["account_last4"] = m.group(1)

    m = re.search(r"Current transaction amount\s*:\s*INR\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if m:
        out["amount"] = _to_float(m.group(1))

    m = re.search(r"Maximum transaction amount\s*:\s*INR\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if m:
        out["extras"]["max_amount"] = _to_float(m.group(1))

    m = re.search(r"Frequency\s*:\s*([^\n]+?)\s*(?:Start date|End date|$)", text, re.IGNORECASE)
    if m:
        out["extras"]["frequency"] = m.group(1).strip()

    m = re.search(r"SI Hub ID\s*:\s*(\S+)", text, re.IGNORECASE)
    if m:
        out["reference_number"] = m.group(1)

    return out


def balance_update_bank_account_null(text: str) -> dict:
    """e.g. 'The balance in your account ending XX2345 has dropped below
    Rs. INR 5,000.00 ... Balance as of yesterday: Rs. INR 78.71 ...'"""
    out = _base_result("balance_update", "bank_account", None)

    m = re.search(r"account ending\s*(?:XX)?(\d{4})", text, re.IGNORECASE)
    if m:
        out["account_last4"] = m.group(1)

    m = re.search(r"dropped below\s+Rs\.?\s*INR\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if m:
        out["extras"]["threshold"] = _to_float(m.group(1))

    m = re.search(r"Balance as of yesterday\s*:\s*Rs\.?\s*INR\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if m:
        out["extras"]["balance"] = _to_float(m.group(1))

    return out


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

PARSERS: dict[tuple[str, str, str], Callable[[str], dict]] = {
    ("credit", "bank_account", "upi"): credit_bank_account_upi,
    ("reversal", "credit_card", "credit_card"): reversal_credit_card_credit_card,
    ("debit", "bank_account", "upi"): debit_bank_account_upi,
    ("debit", "bank_account", "debit_card"): debit_bank_account_debit_card,
    ("debit", "credit_card", "upi"): debit_credit_card_upi,
    ("debit", "credit_card", "credit_card"): debit_credit_card_credit_card,
    ("auto payment", "credit_card", "credit_card"): auto_payment_credit_card_credit_card,
    ("auto payment", "bank_account", "debit_card"): auto_payment_bank_account_debit_card,
    ("balance_update", "bank_account", None): balance_update_bank_account_null,
}


def parse_text(text: str) -> dict:
    """Classify and parse a single raw email text."""
    key = classify(text)
    parser = PARSERS.get(key)
    if parser is None:
        raise ValueError(f"No parser registered for {key}")
    return parser(text)


def parse_texts(texts: list[str]) -> list[dict]:
    return [parse_text(t) for t in texts]


# ---------------------------------------------------------------------------
# Entrypoint / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Demo: load the sample JSON, strip out ONLY the raw `text` fields
    # (simulating real input: plain text, no type/instrument/channel hints),
    # then run them through the classifier + parsers.
    with SAMPLE_JSON.open("r", encoding="utf-8") as f:
        records = json.load(f)

    raw_texts = [r["text"] for r in records]
    parsed = parse_texts(raw_texts)

    print(json.dumps(parsed, indent=2, ensure_ascii=False))
