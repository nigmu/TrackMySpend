"""Bank-agnostic fallback parser for transaction emails.

Returns:
- type: credit / debit / reversal / refund / emi / interest /
        auto payment / balance_update / Not a Transaction
- amount: integer paisa (0 when no amount applies)
"""

from __future__ import annotations

import re

_AMOUNT_RE = re.compile(
    r"(?i)(?:rs\.?\s*(?:inr\s+)?|inr\s+)([\d,]+(?:\.\d+)?)",
)


def _parse_amount(text: str) -> int:
    """Extract the first monetary amount in rupees and return it as integer paisa."""
    m = _AMOUNT_RE.search(text)
    if not m:
        return 0
    rupees = float(m.group(1).replace(",", ""))
    return int(round(rupees * 100))


def transaction_type(text: str) -> str:
    """Classify email text into a transaction type."""
    normalized = text.lower()

    if "dropped below" in normalized and "balance" in normalized:
        return "balance_update"

    if "e-mandate" in normalized or "auto payment" in normalized:
        return "auto payment"

    if "transaction reversal" in normalized or "reversal of rs" in normalized:
        return "reversal"

    if "refund" in normalized:
        return "refund"

    if "emi" in normalized or "installment" in normalized or "instalment" in normalized:
        return "emi"

    if "interest credited" in normalized or "interest of rs" in normalized:
        return "interest"

    if "credited" in normalized or (
        "credit" in normalized and "credit card" not in normalized
    ):
        return "credit"

    if "debited" in normalized or (
        ("debit" in normalized or "spent" in normalized)
        and "debit card" not in normalized
    ):
        return "debit"

    if "debited" in normalized or "debit" in normalized:
        return "debit"

    return "Not a Transaction"


def parse_text(text: str) -> dict:
    """Return transaction type and amount in paisa."""
    txn_type = transaction_type(text)
    if txn_type == "Not a Transaction":
        return {"type": txn_type, "amount": 0}
    if txn_type in ("balance_update", "auto payment", "interest"):
        return {"type": txn_type, "amount": 0}
    return {"type": txn_type, "amount": _parse_amount(text)}


def parse_texts(texts: list[str]) -> list[dict]:
    return [parse_text(text) for text in texts]


def payment_medium(text: str) -> str | None:
    """Return credit_card, debit_card, or upi when mentioned; else None."""
    normalized = text.lower()
    if "credit card" in normalized:
        return "credit_card"
    if "debit card" in normalized:
        return "debit_card"
    if "upi" in normalized:
        return "upi"
    return None