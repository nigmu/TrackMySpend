"""Very basic MVP parser for transaction direction only.

Tracks two things:
- type: "credit", "debit", or "Not a Transaction"
- amount: integer paisa (no decimal places)
"""

from __future__ import annotations

import re

# First rupee amount after Rs. / INR (supports 36.60, 54, 78, 23, 5,000.00, Rs. INR 78.71, etc.)
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


def parse_text(text: str) -> dict:
    """Return whether a transaction text is credit or debit and the amount in paisa."""
    normalized = text.lower()

    if "credited" in normalized or "credit" in normalized and "credit card" not in normalized:
        return {"type": "credit", "amount": _parse_amount(text)}

    if "debited" in normalized or "debit" in normalized and "debit card" not in normalized:
        return {"type": "debit", "amount": _parse_amount(text)}

    return {"type": "Not a Transaction", "amount": 0}


def parse_texts(texts: list[str]) -> list[dict]:
    return [parse_text(text) for text in texts]
