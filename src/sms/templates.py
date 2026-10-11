"""Ordered HDFC SMS templates. First full match wins. No scores.

Categories with count 0 in samples/hdfc_categories.json are absent on purpose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CODE = r"(?:XXXXXX|\d{6})"


@dataclass(frozen=True)
class Template:
    name: str
    kind: str  # ignore | info | debit | credit | bill_reminder
    pattern: re.Pattern[str]
    instrument: str | None = None
    amount_optional: bool = False


def _t(
    name: str,
    kind: str,
    pattern: str,
    instrument: str | None = None,
    amount_optional: bool = False,
) -> Template:
    return Template(
        name,
        kind,
        re.compile(pattern),
        instrument,
        amount_optional,
    )


# Specific wording before general wording. Ignore and info first so a money
# template cannot claim an OTP, a balance, or reward points.
TEMPLATES: tuple[Template, ...] = (
    _t(
        "card_otp",
        "ignore",
        rf"\AOTP is {_CODE} for txn of INR .+ on HDFC Bank card ending \d+",
    ),
    _t(
        "netbanking_otp",
        "ignore",
        rf"OTP to login is {_CODE}",
    ),
    _t(
        "chat_banking_otp",
        "ignore",
        rf"{_CODE} is your OTP, valid for",
    ),
    _t(
        "credit_card_product_otp",
        "ignore",
        rf"{_CODE} is your SECRET One Time Password \(OTP\)",
    ),
    _t(
        "credit_card_declined",
        "ignore",
        r"\AYour transaction on HDFC Bank card .+ is declined",
    ),
    _t("balance_alert", "info", r"\AAvailable Bal in HDFC Bank A/c "),
    _t("login_alert", "info", r"\ALogin Alert!"),
    _t(
        "netbanking_password_reset",
        "info",
        r"IPIN \(Password\) reset is complete",
    ),
    _t(
        "chat_banking_registered",
        "info",
        r"\AYou have successfully registered for HDFC Bank Chat Banking",
    ),
    _t("reward_points", "info", r"\AReward Points Credited:"),
    _t("rm_call", "info", r"your HDFC Bank RM tried reaching you"),
    _t(
        "upi_biometric_disabled",
        "info",
        r"\AUPI Biometric Authentication has been disabled",
    ),
    _t(
        "upi_biometric_enabled",
        "info",
        r"\AUPI Biometric Authentication has been enabled",
    ),
    _t("credit_card_autopay_active", "info", r"\AAutoPay Active!"),
    # Txn Rs … by UPI before Spent Rs.
    _t(
        "credit_card_upi_txn",
        "debit",
        r"\ATxn (?P<amount>Rs\.[\d,]+(?:\.\d+)?)\s+"
        r"On HDFC Bank Card (?P<mask>\d+)\s+"
        r"At (?P<who>.+?)\s+"
        r"by UPI (?P<ref>\d+)\s+"
        r"On (?P<when>\d{2}-\d{2})\b",
        "credit_card",
    ),
    _t(
        "credit_card_spend",
        "debit",
        r"\ASpent (?P<amount>Rs\.[\d,]+(?:\.\d+)?) On HDFC Bank Card "
        r"(?P<mask>\d+) At (?P<who>.+?) On "
        r"(?P<when>\d{4}-\d{2}-\d{2}:\d{2}:\d{2}:\d{2})",
        "credit_card",
    ),
    _t(
        "credit_card_contactless_debit",
        "debit",
        r"\A(?P<amount>Rs\.[\d,]+(?:\.\d+)?) without OTP/PIN HDFC Bank Card "
        r"(?P<mask>x\d+) At (?P<who>.+?) On "
        r"(?P<when>\d{4}-\d{2}-\d{2}:\d{2}:\d{2}:\d{2})",
        "credit_card",
    ),
    _t(
        "credit_card_emandate_success",
        "debit",
        r"\AAutoPay \(E-mandate\) Success!\s+For (?P<who>\S+)\s+"
        r"(?P<amount>Txn Amt:INR[\d,]+(?:\.\d+)?)\s+"
        r"Dt:(?P<when>\d{2}/\d{2}/\d{4})\s+"
        r"Via:HDFC Bank CC (?P<mask>\d+)\s+"
        r"Mandate ID:\s*(?P<ref>\S+)",
        "credit_card",
    ),
    _t(
        "credit_card_autopay_upcoming",
        "bill_reminder",
        r"\AAlert:\s+(?P<amount>INR\.[\d,]+(?:\.\d+)?) will be debited on "
        r"(?P<when>\d{2}/\d{2}/\d{4}) from HDFC Bank Card (?P<mask>\d+) for "
        r"(?P<who>\S+)\s+ID:\s*(?P<ref>\S+)",
        "credit_card",
    ),
    _t(
        "credit_card_refund",
        "credit",
        r"\AAlert! (?P<amount>Rs\.\s*[\d,]+(?:\.\d+)?) refunded by "
        r"(?P<who>.+?) on (?P<when>\d{2}/[A-Z]{3}/\d{4}) & adjusted against "
        r"HDFC Bank Credit Card (?P<mask>\d+)",
        "credit_card",
    ),
    # All-caps payment carries available limit. Its own template, before the
    # sentence-case card payments.
    _t(
        "credit_card_payment_received",
        "credit",
        r"\ADEAR HDFCBANK CARDMEMBER, PAYMENT OF "
        r"(?P<amount>Rs\.\s*[\d,]+(?:\.\d+)?) RECEIVED TOWARDS YOUR CREDIT "
        r"CARD ENDING WITH (?P<mask>\d+) ON "
        r"(?P<when>\d{1,2}-\d{1,2}-\d{4})\.YOUR AVAILABLE LIMIT IS",
        "credit_card",
    ),
    _t(
        "credit_card_online_payment",
        "credit",
        r"\AHDFC Bank Cardmember, Online Payment of "
        r"(?P<amount>Rs\.[\d,]+(?:\.\d+)?) vide Ref# (?P<ref>\S+) was "
        r"credited to your card ending (?P<mask>\d+) On "
        r"(?P<when>\d{2}/[A-Z]{3}/\d{4})_value Date",
        "credit_card",
    ),
    _t(
        "credit_card_payment_credited",
        "credit",
        r"\AHDFC Bank Cardmember, Payment of "
        r"(?P<amount>Rs\s+[\d,]+(?:\.\d+)?) was credited to your card ending "
        r"(?P<mask>\d+) on (?P<when>\d{2}/[A-Z]{3}/\d{4})",
        "credit_card",
    ),
    _t(
        "upi_mandate_debit",
        "debit",
        r"\AUPI Mandate:\s+Sent (?P<amount>Rs\.[\d,]+(?:\.\d+)?)\s+"
        r"from HDFC Bank A/c (?P<mask>\d+)\s+"
        r"To (?P<who>.+)\s+"
        r"(?P<when>\d{2}/\d{2}/\d{2})\s+"
        r"Ref (?P<ref>\d+)",
        "upi",
    ),
    _t(
        "upi_debit",
        "debit",
        r"\ASent (?P<amount>Rs\.[\d,]+(?:\.\d+)?)\s+"
        r"From HDFC Bank A/C (?P<mask>\*\d+)\s+"
        r"To (?P<who>.+)\s+"
        r"On (?P<when>\d{2}/\d{2}/\d{2})\s+"
        r"Ref (?P<ref>\d+)",
        "upi",
    ),
    _t(
        "upi_credit",
        "credit",
        r"\ACredit Alert!\s+(?P<amount>Rs\.[\d,]+(?:\.\d+)?) credited to "
        r"HDFC Bank A/c (?P<mask>\S+) on (?P<when>\d{2}-\d{2}-\d{2}) from VPA "
        r"(?P<who>\S+) \(UPI (?P<ref>\d+)\)",
        "upi",
    ),
    _t(
        "emandate_upcoming",
        "bill_reminder",
        r"\AE-Mandate!\s+(?P<amount>Rs\.[\d,]+(?:\.\d+)?) will be deducted on "
        r"(?P<when>\d{2}/\d{2}/\d{2}, \d{2}:\d{2}:\d{2})\s+"
        r"For (?P<who>.+) mandate\s+UMN (?P<ref>\S+)",
        "upi",
    ),
    _t(
        "salary_credit",
        "credit",
        r"\AUpdate! (?P<amount>INR [\d,]+\.\d+) deposited in HDFC Bank A/c "
        r"(?P<mask>\S+) on (?P<when>\d{2}-[A-Z]{3}-\d{2}) for "
        r"(?P<who>\S.*?SALARY[^.]*?)\.Avl bal ",
        "account",
    ),
    _t(
        "rd_installment_due",
        "bill_reminder",
        r"\ARD Installment Due! Amount (?P<amount>INR [\d,]+\.\d+) Due on "
        r"(?P<when>\d{2}-[A-Z]{3}-\d{2}) HDFC Bank RD (?P<mask>\S+)",
        "rd",
    ),
    _t(
        "credit_card_statement",
        "bill_reminder",
        r"\AStatement Generated:\s+For HDFC Bank Credit Card (?P<mask>\S+)\.",
        "credit_card",
        amount_optional=True,
    ),
)
