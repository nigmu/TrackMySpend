"""Ledger rows in transactions_sms.

Apply inserts or overwrites an SMS ledger row. It does not delete.
Create, update, and delete work by ledger id. This module does not read
or update raw_sms_data.
"""

from __future__ import annotations

from psycopg import Connection

KINDS = frozenset({"debit", "credit", "bill_reminder", "balance"})

_TEXT = ("instrument", "account_mask", "counterparty", "reference")

_PATCH_COLUMNS = (
    "kind",
    "amount_paisa",
    "instrument",
    "account_mask",
    "counterparty",
    "reference",
    "sms_received_at",
)

LEDGER_FROM = """
SELECT t.id, t.raw_sms_id, t.kind, t.amount_paisa, t.instrument,
       t.account_mask, t.counterparty, t.reference, t.sms_received_at,
       t.template_name, t.created_at, t.updated_at, r.sender, r.device_id
FROM transactions_sms t
LEFT JOIN raw_sms_data r ON r.id = t.raw_sms_id
"""


class LedgerRuleError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _require_amount(kind: str, amount: int | None) -> None:
    if kind != "bill_reminder" and amount is None:
        raise LedgerRuleError("amount_paisa is required")


def get(conn: Connection, txn_id: int) -> dict | None:
    return conn.execute(LEDGER_FROM + " WHERE t.id = %s", (txn_id,)).fetchone()


def get_by_raw(conn: Connection, raw_sms_id: int) -> dict | None:
    return conn.execute(
        LEDGER_FROM + " WHERE t.raw_sms_id = %s",
        (raw_sms_id,),
    ).fetchone()


def apply(conn: Connection, raw_sms_id: int, ledger, sms_received_at) -> dict | None:
    """Insert or overwrite the ledger row for this raw SMS. Never deletes.

    Keeps id and created_at on update. Overwrites fields even when they were
    edited by hand. A classification with no ledger writes nothing. A manual
    row has no raw_sms_id, so it is not this row.
    """
    if ledger is None:
        return None
    conn.execute(
        """
        INSERT INTO transactions_sms (
            raw_sms_id, kind, amount_paisa, instrument, account_mask,
            counterparty, reference, sms_received_at, template_name
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (raw_sms_id) DO UPDATE SET
            kind = EXCLUDED.kind,
            amount_paisa = EXCLUDED.amount_paisa,
            instrument = EXCLUDED.instrument,
            account_mask = EXCLUDED.account_mask,
            counterparty = EXCLUDED.counterparty,
            reference = EXCLUDED.reference,
            sms_received_at = EXCLUDED.sms_received_at,
            template_name = EXCLUDED.template_name,
            updated_at = NOW()
        """,
        (
            raw_sms_id,
            ledger.kind,
            ledger.amount_paisa,
            _blank(ledger.instrument),
            _blank(ledger.account_mask),
            _blank(ledger.counterparty),
            _blank(ledger.reference),
            sms_received_at,
            ledger.template_name,
        ),
    )
    return get_by_raw(conn, raw_sms_id)


def create_manual(conn: Connection, fields: dict) -> dict:
    kind = fields.get("kind")
    if kind not in KINDS:
        raise LedgerRuleError("kind is required")
    if "sms_received_at" in fields and fields["sms_received_at"] is None:
        raise LedgerRuleError("sms_received_at is required")
    amount = fields.get("amount_paisa")
    _require_amount(kind, amount)
    row = conn.execute(
        """
        INSERT INTO transactions_sms (
            kind, amount_paisa, instrument, account_mask, counterparty, reference,
            sms_received_at, template_name, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), 'manual', NOW(), NOW())
        RETURNING id
        """,
        (
            kind,
            amount,
            _blank(fields.get("instrument")),
            _blank(fields.get("account_mask")),
            _blank(fields.get("counterparty")),
            _blank(fields.get("reference")),
            fields.get("sms_received_at"),
        ),
    ).fetchone()
    return get(conn, int(row["id"]))


def update(conn: Connection, txn_id: int, fields: dict) -> dict | None:
    if "kind" in fields and fields["kind"] not in KINDS:
        raise LedgerRuleError("kind is required")
    if "sms_received_at" in fields and fields["sms_received_at"] is None:
        raise LedgerRuleError("sms_received_at is required")
    existing = get(conn, txn_id)
    if existing is None:
        return None
    kind = fields.get("kind", existing["kind"])
    amount = fields["amount_paisa"] if "amount_paisa" in fields else existing["amount_paisa"]
    _require_amount(kind, amount)
    sets = []
    params: list = []
    for column in _PATCH_COLUMNS:
        if column not in fields:
            continue
        value = fields[column]
        if column in _TEXT:
            value = _blank(value)
        sets.append(f"{column} = %s")
        params.append(value)
    sets.append("updated_at = NOW()")
    params.append(txn_id)
    result = conn.execute(
        f"UPDATE transactions_sms SET {', '.join(sets)} WHERE id = %s",
        params,
    )
    if result.rowcount == 0:
        return None
    return get(conn, txn_id)


def delete(conn: Connection, txn_id: int) -> bool:
    result = conn.execute(
        "DELETE FROM transactions_sms WHERE id = %s",
        (txn_id,),
    )
    return result.rowcount > 0
