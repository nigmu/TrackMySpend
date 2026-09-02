"""Extract the first rupee amount from text and return integer paisa.

Source-agnostic: used today by the mail pipeline (src/mail/parse.py). Any
future SMS transaction parser should reuse this directly rather than
duplicating it, since bank SMS and bank email alerts use the same
"Rs./INR <amount>" phrasing.
"""

from __future__ import annotations

import re

_AMOUNT_RE = re.compile(r"(?i)(?:rs\.?\s*|inr\s+)([\d,]+(?:\.\d+)?)")


def parse_amount_paisa(text: str) -> int | None:
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    rupees = float(m.group(1).replace(",", ""))
    return int(round(rupees * 100))


if __name__ == "__main__":
    assert parse_amount_paisa("Rs. 1,234.56 debited") == 123456
    assert parse_amount_paisa("INR 500 credited") == 50000
    assert parse_amount_paisa("hello there") is None
    print("amount parser ok")
