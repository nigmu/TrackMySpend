"""Regex rows and the Jev questions that check them.

Jev never sees amount_paisa. A stored 100 becomes the statement "1.00 rupees",
because the SMS writes Rs.1.00.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.sms.classify import classify_sms
from src.sms.templates import TEMPLATES

FIELDS = ("amount_paisa", "account_mask", "counterparty", "reference")
# noul is P(yes). At or above this line the cell is TRUE.
TRUE_AT = 0.5

_CATEGORIES = Path(__file__).resolve().parent.parent / "samples" / "hdfc_categories.json"

_ABSENT = {
    "amount_paisa": (
        "No amount of money that moved or is scheduled to move should be stored "
        "from this SMS. An available balance, a credit limit, or a reward-point "
        "count does not count."
    ),
    "account_mask": "No account or card ending should be stored from this SMS.",
    "counterparty": "No counterparty should be stored from this SMS.",
    "reference": (
        "No transaction reference should be stored from this SMS. A helpline "
        "phone number, a card ending, or an OTP is not a reference."
    ),
}

_PRESENT = {
    "account_mask": "Is `stored` the account or card ending, copied as this SMS writes it?",
    "counterparty": "Is `stored` the other party the money went to or came from?",
    "reference": (
        "Is `stored` the transaction reference? A helpline phone number, a card "
        "ending, or an OTP is not the reference."
    ),
}


def paisa_as_rupees(paisa: int) -> str:
    sign = "-" if paisa < 0 else ""
    paisa = abs(paisa)
    return f"{sign}{paisa // 100}.{paisa % 100:02d}"


def pct(probability: float) -> str:
    return f"{probability * 100:.1f}%"


def jev_mark(noul: float) -> str:
    """TRUE/FALSE plus the probability of that label. noul is P(yes)."""
    if noul >= TRUE_AT:
        return f"TRUE ({pct(noul)})"
    return f"FALSE ({pct(1 - noul)})"


def regex_row(body: str) -> tuple[str, dict[str, str]]:
    """Template id (or unmatched) and the four stored fields. Blank means absent."""
    result = classify_sms(body)
    label = result.category_id or "unmatched"
    ledger = result.ledger
    if ledger is None:
        return label, {name: "" for name in FIELDS}
    amount = ledger.amount_paisa
    return label, {
        "amount_paisa": "" if amount is None else str(amount),
        "account_mask": ledger.account_mask or "",
        "counterparty": ledger.counterparty or "",
        "reference": ledger.reference or "",
    }


def class_criteria() -> dict[str, str]:
    data = json.loads(_CATEGORIES.read_text(encoding="utf-8"))
    summaries = {category["id"]: category["summary"] for category in data["categories"]}
    criteria = {
        template.name: summaries.get(template.name, template.name) for template in TEMPLATES
    }
    criteria["unmatched"] = "None of these templates describe this message."
    return criteria


def noul_question(field: str, value: str) -> dict:
    if not value:
        return {"type": "noul", "instructions": _ABSENT[field]}
    if field == "amount_paisa":
        return {
            "type": "noul",
            "instructions": {
                "stored_rupees": paisa_as_rupees(int(value)),
                "question": (
                    "Is `stored_rupees` the available balance, when this SMS only "
                    "reports a balance, or the amount of money that moved or is "
                    "scheduled to move? A credit limit, a reward-point count, or "
                    "an available balance quoted beside a debit or credit does not count."
                ),
            },
        }
    return {
        "type": "noul",
        "instructions": {"stored": value, "question": _PRESENT[field]},
    }


def questions_for(fields: dict[str, str]) -> dict:
    criteria = class_criteria()
    questions = {
        "class": {
            "type": "choice",
            "instructions": "Which template describes this HDFC Bank SMS?",
            "criteria": criteria,
        }
    }
    for field in FIELDS:
        questions[field] = noul_question(field, fields[field])
    return questions
