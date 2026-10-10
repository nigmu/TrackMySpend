"""Classify one HDFC SMS body, and apply that result to a raw_sms_data row.

No API route calls these. POST /sms/ingest only stores the raw message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from psycopg import Connection

from .amount import parse_amount_paisa
from .templates import TEMPLATES, Template

# ponytail: fixed +05:30; India has no daylight saving. Upgrade path is a
# named zone if a template is ever for a bank SMS outside India.
_IST = timezone(timedelta(hours=5, minutes=30))

_MON = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


@dataclass(frozen=True)
class SmsLedger:
    kind: str
    amount_paisa: int | None
    instrument: str | None
    account_mask: str | None
    counterparty: str | None
    reference: str | None
    occurred_at: datetime | None
    template_name: str


@dataclass(frozen=True)
class SmsClassification:
    category_id: str | None
    processing_status: str  # done | ignored | unmatched
    ledger: SmsLedger | None = None


def _year2(text: str) -> int:
    # ponytail: two-digit years are 2000-2099. Upgrade path is a four-digit
    # year in the template capture.
    return 2000 + int(text)


def _at(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=_IST)


def parse_sms_when(text: str) -> datetime | None:
    """Clock time in the SMS, else midnight +05:30. Day-month with no year is None."""
    text = text.strip()
    # credit_card_upi_txn writes "On 02-10". The year is not in the SMS.
    if re.fullmatch(r"\d{2}-\d{2}", text):
        return None
    try:
        matched = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2}):(\d{2}):(\d{2}):(\d{2})", text)
        if matched:
            year, month, day, hour, minute, second = (int(part) for part in matched.groups())
            return _at(year, month, day, hour, minute, second)
        matched = re.fullmatch(r"(\d{2})/(\d{2})/(\d{2}), (\d{2}):(\d{2}):(\d{2})", text)
        if matched:
            day, month, year, hour, minute, second = matched.groups()
            return _at(_year2(year), int(month), int(day), int(hour), int(minute), int(second))
        matched = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", text)
        if matched:
            day, month, year = matched.groups()
            return _at(int(year), int(month), int(day))
        matched = re.fullmatch(r"(\d{2})/([A-Z]{3})/(\d{4})", text)
        if matched:
            day, month, year = matched.groups()
            return _at(int(year), _MON[month], int(day))
        matched = re.fullmatch(r"(\d{2})-([A-Z]{3})-(\d{2})", text)
        if matched:
            day, month, year = matched.groups()
            return _at(_year2(year), _MON[month], int(day))
        matched = re.fullmatch(r"(\d{2})/(\d{2})/(\d{2})", text)
        if matched:
            day, month, year = matched.groups()
            return _at(_year2(year), int(month), int(day))
        matched = re.fullmatch(r"(\d{2})-(\d{2})-(\d{2})", text)
        if matched:
            day, month, year = matched.groups()
            return _at(_year2(year), int(month), int(day))
        matched = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", text)
        if matched:
            day, month, year = matched.groups()
            return _at(int(year), int(month), int(day))
    except (KeyError, ValueError):
        return None
    return None


def _field(match, name: str) -> str | None:
    value = match.groupdict().get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _ledger(template: Template, match) -> SmsLedger | None:
    groups = match.groupdict()
    span = groups.get("amount")
    if span is None:
        amount = None
        if not template.amount_optional:
            return None
    else:
        amount = parse_amount_paisa(span)
        if amount is None:
            return None
    when_text = groups.get("when")
    if when_text is None:
        occurred = None
    else:
        occurred = parse_sms_when(when_text)
        if occurred is None and not template.when_optional:
            return None
    return SmsLedger(
        kind=template.kind,
        amount_paisa=amount,
        instrument=template.instrument,
        account_mask=_field(match, "mask"),
        counterparty=_field(match, "who"),
        reference=_field(match, "ref"),
        occurred_at=occurred,
        template_name=template.name,
    )


def classify_sms(body: str) -> SmsClassification:
    """First matching template. No ledger fields for ignore or info."""
    for template in TEMPLATES:
        match = template.pattern.search(body)
        if match is None:
            continue
        if template.kind == "ignore":
            return SmsClassification(template.name, "ignored", None)
        if template.kind == "info":
            return SmsClassification(template.name, "done", None)
        ledger = _ledger(template, match)
        if ledger is None:
            # Wording matched but the amount span did not parse. Do not guess
            # and do not fall through to a looser template.
            return SmsClassification(None, "unmatched", None)
        return SmsClassification(template.name, "done", ledger)
    return SmsClassification(None, "unmatched", None)


def apply_sms_classification(
    conn: Connection,
    raw_sms_id: int,
    result: SmsClassification,
) -> None:
    """Set processing_status and, when result.ledger is set, insert one transactions_sms row.

    Does not commit. Insert runs before the status update, so a failed insert
    leaves the raw row unchanged.
    """
    ledger = result.ledger
    if ledger is not None:
        conn.execute(
            """
            INSERT INTO transactions_sms (
                raw_sms_id, kind, amount_paisa, instrument, account_mask,
                counterparty, reference, occurred_at, template_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                raw_sms_id,
                ledger.kind,
                ledger.amount_paisa,
                ledger.instrument,
                ledger.account_mask,
                ledger.counterparty,
                ledger.reference,
                ledger.occurred_at,
                ledger.template_name,
            ),
        )
    conn.execute(
        """
        UPDATE raw_sms_data
        SET processing_status = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (result.processing_status, raw_sms_id),
    )
