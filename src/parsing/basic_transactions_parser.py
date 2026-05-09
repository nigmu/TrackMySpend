"""Very basic MVP parser for transaction direction only.

This parser intentionally tracks only one thing:
- type: "credit" or "debit"
"""

from __future__ import annotations

import re

# First rupee amount after Rs. / INR (supports 36.60, 54, 78, 23, 5,000.00, Rs. INR 78.71, etc.)
def _parse_amount(text: str) -> int:
    # Extract the first monetary amount in rupees and return it as integer paisa
    r =  re.compile(r"(?i)(?:rs\.?\s*(?:inr\s+)?|inr\s+)([\d,]+(?:\.\d+)?)",)
    m = r.search(text)
    if not m:
        return 0
    rupees = float(m.group(1).replace(',', ''))
    return int(round(rupees * 100))


def parse_text(text: str) -> dict:
    """Return whether a transaction text is credit or debit and the amount.

    Rules (simple MVP):
    - If text contains "credit", "credited", but ignore the word "credit card" and it conatains the word "Rs."
        - then return credit and the amount
    - If text contains "debit", "debited", but ignore the word "debit card" and it conatains the word "Rs."
        - then return debit and the amount
    - Else default to "Not a Transaction"
        - then return 0
    -
    """
    normalized = text.lower()

    if "credited" in normalized or "credit" in normalized and "credit card" not in normalized:
        return {"type": "credit", "amount": _parse_amount(text)}

    if "debited" in normalized or "debit" in normalized and "debit card" not in normalized:
        return {"type": "debit", "amount": _parse_amount(text)}

    return {"type": "Not a Transaction", "amount": 0}


def parse_texts(texts: list[str]) -> list[dict]:
    """Parse a list of transaction texts."""
    return [parse_text(text) for text in texts]
