"""Pytest suite for the advanced HDFC parser."""

import json
from pathlib import Path

from ..advanced_hdfc import parse_text

SAMPLE_JSON = Path(__file__).resolve().parents[1] / "SAMPLE_MAILS" / "HDFC.json"


def load_sample_texts():
    with SAMPLE_JSON.open("r", encoding="utf-8") as f:
        records = json.load(f)
    return [r["text"] for r in records]


def test_parse_all_hdfc_samples():
    texts = load_sample_texts()
    results = [parse_text(text) for text in texts]

    assert len(results) == 9

    assert results[0] == {
        "bank": "HDFC",
        "type": "credit",
        "instrument": "bank_account",
        "channel": "upi",
        "amount": 240.0,
        "currency": "INR",
        "account_last4": "1111",
        "counterparty": "SAMPLE PERSON NAME",
        "counterparty_vpa": "demo.payer.sample@okaxis",
        "reference_number": "900000000001",
        "extras": {},
    }

    assert results[1] == {
        "bank": "HDFC",
        "type": "reversal",
        "instrument": "credit_card",
        "channel": "credit_card",
        "amount": 14.35,
        "currency": "INR",
        "account_last4": "2222",
        "counterparty": "SAMPLE RIDESHARE INDIA PVT L",
        "counterparty_vpa": None,
        "reference_number": None,
        "extras": {},
    }

    assert results[2] == {
        "bank": "HDFC",
        "type": "debit",
        "instrument": "bank_account",
        "channel": "upi",
        "amount": 28.5,
        "currency": "INR",
        "account_last4": "1111",
        "counterparty": "DEMO METRO TRANSIT",
        "counterparty_vpa": "metro.sample.demo@hdfcbank",
        "reference_number": "900000000002",
        "extras": {},
    }

    assert results[3] == {
        "bank": "HDFC",
        "type": "debit",
        "instrument": "bank_account",
        "channel": "debit_card",
        "amount": 120.0,
        "currency": "INR",
        "account_last4": "3333",
        "counterparty": "SAMPLE HYPERMARKET",
        "counterparty_vpa": None,
        "reference_number": None,
        "extras": {},
    }

    assert results[4] == {
        "bank": "HDFC",
        "type": "debit",
        "instrument": "credit_card",
        "channel": "upi",
        "amount": 214.0,
        "currency": "INR",
        "account_last4": "4444",
        "counterparty": "SAMPLE FOOD APP",
        "counterparty_vpa": "foodorder.demo@payment",
        "reference_number": "900000000003",
        "extras": {},
    }

    assert results[5] == {
        "bank": "HDFC",
        "type": "debit",
        "instrument": "credit_card",
        "channel": "credit_card",
        "amount": 259.0,
        "currency": "INR",
        "account_last4": "4444",
        "counterparty": "SAMPLE BRAND PRIVATE",
        "counterparty_vpa": None,
        "reference_number": None,
        "extras": {},
    }

    assert results[6] == {
        "bank": "HDFC",
        "type": "auto payment",
        "instrument": "credit_card",
        "channel": "credit_card",
        "amount": 299.0,
        "currency": "INR",
        "account_last4": "4444",
        "counterparty": "MUSIC SUB DEMO",
        "counterparty_vpa": None,
        "reference_number": "DUMMYHUB01AA",
        "extras": {
            "max_amount": 299.0,
            "frequency": "just_in_time",
        },
    }

    assert results[7] == {
        "bank": "HDFC",
        "type": "auto payment",
        "instrument": "bank_account",
        "channel": "debit_card",
        "amount": 2.0,
        "currency": "INR",
        "account_last4": "3333",
        "counterparty": "CLOUD SERVICES DEMO",
        "counterparty_vpa": None,
        "reference_number": "DUMMYHUB02BB",
        "extras": {
            "max_amount": 75000.0,
            "frequency": "As Presented",
        },
    }

    assert results[8] == {
        "bank": "HDFC",
        "type": "balance_update",
        "instrument": "bank_account",
        "channel": None,
        "amount": None,
        "currency": "INR",
        "account_last4": "1111",
        "counterparty": None,
        "counterparty_vpa": None,
        "reference_number": None,
        "extras": {
            "threshold": 5000.0,
            "balance": 78.71,
        },
    }
