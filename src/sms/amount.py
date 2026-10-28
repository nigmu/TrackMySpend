"""Paisa from one SMS amount span.

A template captures the transaction amount (for example ``Rs.255.5`` or
``Txn Amt:INR299.00``). This function reads that span only. It does not search
a whole SMS, so a later available balance or credit limit cannot become the
transaction.
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

# Span only: optional "Txn Amt:" label, then Rs/INR, an optional dot, an
# optional space, then the number. fullmatch rejects any surrounding SMS text.
_AMOUNT_RE = re.compile(
    r"(?i)(?:txn\s+amt\s*:)?\s*(?:rs|inr)\.?\s*([\d,]+(?:\.\d+)?)"
)


def parse_amount_paisa(span: str) -> int | None:
    """Return integer paisa for one amount span, or None if it is not one amount."""
    match = _AMOUNT_RE.fullmatch(span.strip())
    if match is None:
        return None
    rupees = Decimal(match.group(1).replace(",", ""))
    paisa = (rupees * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(paisa)
