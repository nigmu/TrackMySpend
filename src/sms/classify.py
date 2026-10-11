"""Classify one HDFC SMS body, and apply that result to a raw_sms_data row.

No API route calls these. POST /sms/ingest only stores the raw message.
"""

from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection

from .amount import parse_amount_paisa
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
            return SmsClassification(None, "unmatched", None)
        return SmsClassification(template.name, "done", ledger)
    return SmsClassification(None, "unmatched", None)


def apply_sms_classification(
    conn: Connection,
    raw_sms_id: int,
    result: SmsClassification,
) -> None:
    """Set processing_status and, when result.ledger is set, insert one transactions_sms row.

    sms_received_at on the ledger row is copied from raw_sms_data.received_at.
    Does not commit. The insert runs before the status update, so a failed
    insert leaves the raw row unchanged.
    """
    ledger = result.ledger
    if ledger is not None:
        raw = conn.execute(
            "SELECT received_at FROM raw_sms_data WHERE id = %s",
            (raw_sms_id,),
        ).fetchone()
        received_at = None if raw is None else raw["received_at"]
        conn.execute(
            """
            INSERT INTO transactions_sms (
                raw_sms_id, kind, amount_paisa, instrument, account_mask,
                counterparty, reference, sms_received_at, template_name
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
                received_at,
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
