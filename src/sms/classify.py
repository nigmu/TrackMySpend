"""Classify one HDFC SMS body, then hand the ledger row to the ledger module.

Routes call parse_new_sms and parse_stored_sms. Ingest classifies a new row
in the same request. POST /sms/parse classifies one stored raw SMS.
classify_sms does not touch the database.
"""

from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection

from .amount import parse_amount_paisa
from . import db
from .ledger import apply
from .templates import TEMPLATES, Template


@dataclass(frozen=True)
class SmsLedger:
    kind: str
    amount_paisa: int | None
    instrument: str | None
    account_mask: str | None
    counterparty: str | None
    reference: str | None
    template_name: str


@dataclass(frozen=True)
class SmsClassification:
    category_id: str | None
    processing_status: str  # done | ignored | unmatched
    ledger: SmsLedger | None = None
    reason: str | None = None  # no_template | amount_unparsed
    template: str | None = None  # set when wording matched but the amount did not


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
    return SmsLedger(
        kind=template.kind,
        amount_paisa=amount,
        instrument=template.instrument,
        account_mask=_field(match, "mask"),
        counterparty=_field(match, "who"),
        reference=_field(match, "ref"),
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
            return SmsClassification(
                None, "unmatched", None, "amount_unparsed", template.name
            )
        return SmsClassification(template.name, "done", ledger)
    return SmsClassification(None, "unmatched", None, "no_template")


def _write_classification(
    conn: Connection,
    raw_sms_id: int,
    body: str,
    sms_received_at,
) -> SmsClassification:
    result = classify_sms(body)
    apply(conn, raw_sms_id, result.ledger, sms_received_at)
    db.set_processing_status(conn, raw_sms_id, result.processing_status)
    return result


def parse_new_sms(conn: Connection, raw_sms_id: int, body: str) -> SmsClassification:
    """Classify a raw SMS that was just stored. received_at is copied from that row."""
    raw = conn.execute(
        "SELECT received_at FROM raw_sms_data WHERE id = %s",
        (raw_sms_id,),
    ).fetchone()
    received_at = None if raw is None else raw["received_at"]
    return _write_classification(conn, raw_sms_id, body, received_at)


def parse_stored_sms(conn: Connection, raw_sms_id: int) -> SmsClassification | None:
    """Classify one stored raw SMS. None when that id is not in raw_sms_data."""
    row = conn.execute(
        "SELECT body, received_at FROM raw_sms_data WHERE id = %s",
        (raw_sms_id,),
    ).fetchone()
    if row is None:
        return None
    return _write_classification(conn, raw_sms_id, row["body"], row["received_at"])
