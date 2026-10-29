"""HDFC SMS classification. Sample strings are the redacted category samples.

The export under src/sms/samples/ is not in git. The count check skips when
that CSV is absent.
"""

from __future__ import annotations

import csv
import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from src.core.config import IST

from src.sms.amount import parse_amount_paisa
from src.sms.classify import classify_sms
from src.sms.ledger import apply
from src.sms.templates import TEMPLATES

# category id, JSON kind, redacted body
SAMPLES = (
    ("card_otp", "ignore", "OTP is XXXXXX for txn of INR 61.71 at UBER INDIA  on HDFC Bank card ending 6517. Valid till  09:54. Do not share OTP for security reasons"),
    ("card_otp", "ignore", "OTP is XXXXXX for txn of INR 164.37 at UBER INDIA  on HDFC Bank card ending 6517. Valid till  04:03. Do not share OTP for security reasons"),
    ("card_otp", "ignore", "OTP is XXXXXX for txn of INR 15701.00 at FlipkartInt on HDFC Bank card ending 6517. Valid till  04:01. Do not share OTP for security reasons"),
    ("netbanking_otp", "ignore", "To keep your HDFC Bank NetBanking experience secure, request you to verify your identity.OTP to login is XXXXXX.Never share OTP.\nNot You?Call us on 18002586161"),
    ("netbanking_otp", "ignore", "To keep your HDFC Bank NetBanking experience secure, request you to verify your identity.OTP to login is XXXXXX.Never share OTP.\nNot You?Call us on 18002586161"),
    ("chat_banking_otp", "ignore", "Dear HDFC Bank Customer, XXXXXX is your OTP, valid for next 15 Minutes to register for Chat Banking on WhatsApp. Please DO NOT disclose it to anyone."),
    ("credit_card_product_otp", "ignore", "XXXXXX is your SECRET One Time Password (OTP) on your HDFC BANK Credit Card transaction for Loan on Card/BTEMI/LE/Upgrade/SmartPay/Insurance. Never Share OTP"),
    ("credit_card_declined", "ignore", "Your transaction on HDFC Bank card for 164.37 at UBER INDIA SYSTEMS PRI is declined due to wrong input of ExpiryDate or CVV. Please try again."),
    ("upi_mandate_debit", "debit", "UPI Mandate:\nSent Rs.50.00\nfrom HDFC Bank A/c 3826\nTo SAFE GOLD\n10/10/26\nRef 628300818456\nNot You? Call 18002586161/SMS BLOCK UPI to 7308080808"),
    ("upi_mandate_debit", "debit", "UPI Mandate:\nSent Rs.50.00\nfrom HDFC Bank A/c 3826\nTo SAFE GOLD\n22/09/26\nRef 626508966188\nNot You? Call 18002586161/SMS BLOCK UPI to 7308080808"),
    ("upi_mandate_debit", "debit", "UPI Mandate:\nSent Rs.50.00\nfrom HDFC Bank A/c 3826\nTo SAFE GOLD\n06/09/26\nRef 624920327411\nNot You? Call 18002586161/SMS BLOCK UPI to 7308080808"),
    ("emandate_upcoming", "reminder", "E-Mandate!\nRs.50.00 will be deducted on 11/10/26, 00:00:00\nFor SAFE GOLD mandate\nUMN 0b7c2aaf0c0448a9b5ef52c8d93391d7@ybl\nMaintain Balance\n-HDFC Bank"),
    ("emandate_upcoming", "reminder", "E-Mandate!\nRs.50.00 will be deducted on 24/09/26, 00:00:00\nFor SAFE GOLD mandate\nUMN 0b7c2aaf0c0448a9b5ef52c8d93391d7@ybl\nMaintain Balance\n-HDFC Bank"),
    ("emandate_upcoming", "reminder", "E-Mandate!\nRs.50.00 will be deducted on 07/09/26, 00:00:00\nFor SAFE GOLD mandate\nUMN 0b7c2aaf0c0448a9b5ef52c8d93391d7@ybl\nMaintain Balance\n-HDFC Bank"),
    ("upi_debit", "debit", "Sent Rs.55.00\nFrom HDFC Bank A/C *3826\nTo PURUJIT GHOSH\nOn 10/10/26\nRef 664906313484\nNot You?\nCall 18002586161/SMS BLOCK UPI to 7308080808"),
    ("upi_debit", "debit", "Sent Rs.40.00\nFrom HDFC Bank A/C *3826\nTo BIKASH KUMAR PARIDA\nOn 16/09/26\nRef 662528048378\nNot You?\nCall 18002586161/SMS BLOCK UPI to 7308080808"),
    ("upi_debit", "debit", "Sent Rs.1.00\nFrom HDFC Bank A/C *3826\nTo GEETA RANI BEHERA\nOn 06/09/26\nRef 661510272598\nNot You?\nCall 18002586161/SMS BLOCK UPI to 7308080808"),
    ("upi_credit", "credit", "Credit Alert!\nRs.25.00 credited to HDFC Bank A/c XX3826 on 10-10-26 from VPA 7044653836@nyes (UPI 005726968001)"),
    ("upi_credit", "credit", "Credit Alert!\nRs.51.36 credited to HDFC Bank A/c XX3826 on 20-09-26 from VPA ritamrajnayak@okicici (UPI 626385871341)"),
    ("upi_credit", "credit", "Credit Alert!\nRs.1.00 credited to HDFC Bank A/c XX3826 on 06-09-26 from VPA 6370227050@yescred (UPI 661500244647)"),
    ("balance_alert", "balance", "Available Bal in HDFC Bank A/c XX3826 as on yesterday:09-OCT-26 is INR 1,040.90. Cheques are subject to clearing.For updated A/C Bal dial 18002703333."),
    ("balance_alert", "balance", "Available Bal in HDFC Bank A/c XX3826 as on yesterday:21-SEP-26 is INR 172.35. Cheques are subject to clearing.For updated A/C Bal dial 18002703333."),
    ("balance_alert", "balance", "Available Bal in HDFC Bank A/c XX3826 as on yesterday:04-SEP-26 is INR 2,617.28. Cheques are subject to clearing.For updated A/C Bal dial 18002703333."),
    ("credit_card_spend", "debit", "Spent Rs.255.5 On HDFC Bank Card 6517 At UBER INDIA SYSTEMS PRI On 2026-10-07:20:54:25.Not You? To Block+Reissue Call 18002586161/SMS BLOCK CC 6517 to 7308080808"),
    ("credit_card_spend", "debit", "Spent Rs.61.71 On HDFC Bank Card 6517 At UBER INDIA SYSTEMS PRI On 2026-10-09:21:51:52.Not You? To Block+Reissue Call 18002586161/SMS BLOCK CC 6517 to 7308080808"),
    ("credit_card_spend", "debit", "Spent Rs.58.34 On HDFC Bank Card 6517 At UBER INDIA SYSTEMS PRI On 2026-09-06:20:49:18.Not You? To Block+Reissue Call 18002586161/SMS BLOCK CC 6517 to 7308080808"),
    ("credit_card_upi_txn", "debit", "Txn Rs.4681.20\nOn HDFC Bank Card 6517\nAt districtdining1.payu@hdfc \nby UPI 664129867836\nOn 02-10\nNot You?\nCall 18002586161/SMS BLOCK CC 6517 to 7308080808"),
    ("credit_card_upi_txn", "debit", "Txn Rs.805.00\nOn HDFC Bank Card 6517\nAt swiggyinstamartecom@axb \nby UPI 662915765457\nOn 20-09\nNot You?\nCall 18002586161/SMS BLOCK CC 6517 to 7308080808"),
    ("credit_card_upi_txn", "debit", "Txn Rs.1221.94\nOn HDFC Bank Card 6517\nAt redbus32.rzp@hdfcbank \nby UPI 661611472358\nOn 07-09\nNot You?\nCall 18002586161/SMS BLOCK CC 6517 to 7308080808"),
    ("credit_card_contactless_debit", "debit", "Rs.299 without OTP/PIN HDFC Bank Card x6517 At SPOTIFYINDIA On 2026-09-14:02:36:34.Not U? Block&Reissue:Call 18002586161/SMS BLOCK CC 6517 to 7308080808"),
    ("credit_card_emandate_success", "debit", "AutoPay (E-mandate) Success!\nFor SPOTIFYINDIA\nTxn Amt:INR299.00\nDt:14/09/2026\nVia:HDFC Bank CC 6517\nMandate ID: YOehxrZiG0\nNot You? To Block+Reissue Call 18002586161/SMS BLOCK CC 6517 to 7308080808"),
    ("credit_card_autopay_upcoming", "reminder", "Alert:\nINR.299.00 will be debited on 13/09/2026 from HDFC Bank Card 6517 for SPOTIFYINDIA\nID:YOehxrZiG0\nAct:https://1.hdfc.bank.in/HDFCBK/s/a/7WwGMw4e"),
    ("credit_card_refund", "credit", "Alert! Rs. 1112 refunded by MYNTRADESIGNSPVTLTD on 06/OCT/2026 & adjusted against HDFC Bank Credit Card 6517 View updated balance here: https://1.hdfc.bank.in/HDFCBK/s/K55LPEMW"),
    ("credit_card_refund", "credit", "Alert! Rs. 1231 refunded by MYNTRADESIGNSPVTLTD on 24/SEP/2026 & adjusted against HDFC Bank Credit Card 6517 View updated balance here: https://1.hdfc.bank.in/HDFCBK/s/5XRL2Awb"),
    ("credit_card_refund", "credit", "Alert! Rs. 2299 refunded by MYNTRADESIGNSPVTLTD on 22/SEP/2026 & adjusted against HDFC Bank Credit Card 6517 View updated balance here: https://1.hdfc.bank.in/HDFCBK/s/Ov3neWMM"),
    ("netbanking_password_reset", "info", "Alert!\nYour HDFC Bank NetBanking IPIN (Password) reset is complete. \nYou''re all set to login.\nNot you? Call 18002586161"),
    ("login_alert", "info", "Login Alert!\nWe noticed that there was a login to your NetBanking.\nIf it wasn''t you, please call us immediately at 18002586161.\nStay secure with HDFC Bank!"),
    ("chat_banking_registered", "info", "You have successfully registered for HDFC Bank Chat Banking on WhatsApp.\nChat here: https://1.hdfc.bank.in/HDFCBK/s/a/322xWXyX\nNot you? Call 18002586161"),
    ("reward_points", "info", "Reward Points Credited: 313 To HDFC Bank Credit Card 6517 On 03/OCT/2026 Towards EARNED 5% CASHBACK_SELECT MERCHANTSCheck Here: https://1.hdfc.bank.in/HDFCBK/s/eqq28Z4w"),
    ("rm_call", "info", "Dear Customer, your HDFC Bank RM tried reaching you from 1600310379. Please call your RM directly on +913366559351. Save contact: https://1.hdfc.bank.in/HDFCBK/s/a/BAAmYX3m"),
    ("credit_card_payment_credited", "credit", "HDFC Bank Cardmember, Payment of Rs 3895.27 was credited to your card ending 6517 on 01/OCT/2026."),
    ("credit_card_online_payment", "credit", "HDFC Bank Cardmember, Online Payment of Rs.2500 vide Ref# 273L4LYMUN9W6B7 was credited to your card ending 6517 On 30/SEP/2026_value Date 30/SEP/2026"),
    ("credit_card_online_payment", "credit", "HDFC Bank Cardmember, Online Payment of Rs.4039 vide Ref# 2730STHWJ7P8YWA was credited to your card ending 6517 On 30/SEP/2026_value Date 30/SEP/2026"),
    ("credit_card_online_payment", "credit", "HDFC Bank Cardmember, Online Payment of Rs.9000 vide Ref# 268DHB3O77BS4OG was credited to your card ending 6517 On 26/SEP/2026_value Date 25/SEP/2026"),
    ("credit_card_payment_received", "credit", "DEAR HDFCBANK CARDMEMBER, PAYMENT OF Rs. 3895.27 RECEIVED TOWARDS YOUR CREDIT CARD ENDING WITH 6517 ON 1-10-2026.YOUR AVAILABLE LIMIT IS RS. 93000.00"),
    ("credit_card_payment_received", "credit", "DEAR HDFCBANK CARDMEMBER, PAYMENT OF Rs. 4039.00 RECEIVED TOWARDS YOUR CREDIT CARD ENDING WITH 6517 ON 30-9-2026.YOUR AVAILABLE LIMIT IS RS. 88956.77"),
    ("credit_card_payment_received", "credit", "DEAR HDFCBANK CARDMEMBER, PAYMENT OF Rs. 9000.00 RECEIVED TOWARDS YOUR CREDIT CARD ENDING WITH 6517 ON 25-9-2026.YOUR AVAILABLE LIMIT IS RS. 82925.86"),
    ("upi_biometric_disabled", "info", "UPI Biometric Authentication has been disabled for\nHDFC Bank A/c 3826.\nContinue using UPI PIN.\nContact 1800 258 6161 for queries."),
    ("upi_biometric_enabled", "info", "UPI Biometric Authentication has been enabled on\ngooglePayApp for A/c 3826.\nUse device biometrics for UPI payments.\nNot you? Contact 1800 258 6161 HDFC Bank"),
    ("credit_card_autopay_active", "info", "AutoPay Active!\nFor Cursor\nStarting:30/09/2026\nMandate ID:Yg28tAy1u9\nOn HDFC Bank Card 6517\nManage: https://1.hdfc.bank.in/HDFCBK/s/a/0kR8WO12\nTnC"),
    ("salary_credit", "credit", "Update! INR 62,679.00 deposited in HDFC Bank A/c XX3826 on 30-SEP-26 for ACH C- SAL-EYGLODELSERINDLL-SALARYSEP26B.Avl bal INR 62,820.32. Cheque deposits in A/C are subject to clearing"),
    ("rd_installment_due", "reminder", "RD Installment Due! Amount INR 2,000.00 Due on 02-OCT-26 HDFC Bank RD XX644 Check RD statement on the MobileBanking App."),
    ("credit_card_statement", "reminder", "Statement Generated:\nFor HDFC Bank Credit Card XX6517.\nView: https://1.hdfc.bank.in/HDFCBK/v/HN4jGT\nPay: https://1.hdfc.bank.in/HDFCBK/v/HN4jGV"),
)

_TEMPLATE_ORDER = (
    "card_otp",
    "netbanking_otp",
    "chat_banking_otp",
    "credit_card_product_otp",
    "credit_card_declined",
    "balance_alert",
    "login_alert",
    "netbanking_password_reset",
    "chat_banking_registered",
    "reward_points",
    "rm_call",
    "upi_biometric_disabled",
    "upi_biometric_enabled",
    "credit_card_autopay_active",
    "credit_card_upi_txn",
    "credit_card_spend",
    "credit_card_contactless_debit",
    "credit_card_emandate_success",
    "credit_card_autopay_upcoming",
    "credit_card_refund",
    "credit_card_payment_received",
    "credit_card_online_payment",
    "credit_card_payment_credited",
    "upi_mandate_debit",
    "upi_debit",
    "upi_credit",
    "emandate_upcoming",
    "salary_credit",
    "rd_installment_due",
    "credit_card_statement",
)

_LEDGER_KIND = {
    "debit": "debit",
    "credit": "credit",
    "reminder": "bill_reminder",
    "balance": "balance",
}

_NO_COUNTERPARTY = {
    "credit_card_payment_received",
    "credit_card_online_payment",
    "credit_card_payment_credited",
    "rd_installment_due",
    "credit_card_statement",
    "balance_alert",
}

_HAS_REFERENCE = {
    "upi_debit",
    "upi_credit",
    "upi_mandate_debit",
    "emandate_upcoming",
    "credit_card_upi_txn",
    "credit_card_emandate_success",
    "credit_card_autopay_upcoming",
    "credit_card_online_payment",
}

_SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
_CSV = _SAMPLES_DIR / "raw_sms_data-1791614970963.csv"
_JSON = _SAMPLES_DIR / "hdfc_categories.json"


def _redact(body: str) -> str:
    text = re.sub(r"(?<!\d)\d{6}(?!\d)", "XXXXXX", body)
    return text.replace("\n", " | ")[:140]


class TestHdfcSmsAmount(unittest.TestCase):
    def test_amount_span_forms(self):
        self.assertEqual(parse_amount_paisa("Rs.61.71"), 6171)
        self.assertEqual(parse_amount_paisa("Rs.255.5"), 25550)
        self.assertEqual(parse_amount_paisa("Rs. 1112"), 111200)
        self.assertEqual(parse_amount_paisa("INR 62,679.00"), 6267900)
        self.assertEqual(parse_amount_paisa("INR.299.00"), 29900)
        self.assertEqual(parse_amount_paisa("Txn Amt:INR299.00"), 29900)
        self.assertEqual(parse_amount_paisa("Rs 3895.27"), 389527)
        whole = (
            "Update! INR 62,679.00 deposited in HDFC Bank A/c XX3826. "
            "Avl bal INR 62,820.32"
        )
        self.assertIsNone(parse_amount_paisa(whole))


class TestHdfcSmsParser(unittest.TestCase):
    def test_template_order(self):
        self.assertEqual(tuple(template.name for template in TEMPLATES), _TEMPLATE_ORDER)
        names = [template.name for template in TEMPLATES]
        self.assertLess(names.index("credit_card_upi_txn"), names.index("credit_card_spend"))
        self.assertLess(names.index("upi_mandate_debit"), names.index("upi_debit"))
        self.assertLess(
            names.index("credit_card_online_payment"),
            names.index("credit_card_payment_credited"),
        )
        self.assertLess(
            names.index("credit_card_payment_received"),
            names.index("credit_card_payment_credited"),
        )

    def test_schema_fk_points_at_raw_sms_data(self):
        schema = (Path(__file__).resolve().parents[1] / "db" / "schema.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("CREATE TABLE IF NOT EXISTS transactions_sms", schema)
        self.assertIn(
            "raw_sms_id BIGINT UNIQUE\n            REFERENCES raw_sms_data (id) ON DELETE CASCADE",
            schema,
        )

    def test_samples_classify_as_their_category(self):
        self.assertGreater(len(SAMPLES), 0)
        seen = set()
        for category_id, json_kind, body in SAMPLES:
            seen.add(category_id)
            result = classify_sms(body)
            self.assertEqual(result.category_id, category_id, _redact(body))
            if json_kind in ("ignore", "info"):
                self.assertIsNone(result.ledger, category_id)
                self.assertEqual(
                    result.processing_status,
                    "ignored" if json_kind == "ignore" else "done",
                )
                self.assertNotIn("XXXXXX", repr(result))
                continue
            self.assertEqual(result.processing_status, "done")
            ledger = result.ledger
            self.assertIsNotNone(ledger)
            self.assertEqual(ledger.kind, _LEDGER_KIND[json_kind])
            self.assertEqual(ledger.template_name, category_id)
            self.assertIsNotNone(ledger.instrument)
            if category_id == "credit_card_statement":
                self.assertIsNone(ledger.amount_paisa)
            else:
                self.assertIsNotNone(ledger.amount_paisa)
            if category_id == "emandate_upcoming":
                self.assertIsNone(ledger.account_mask)
            else:
                self.assertTrue(ledger.account_mask)
            if category_id in _NO_COUNTERPARTY:
                self.assertIsNone(ledger.counterparty)
            else:
                self.assertTrue(ledger.counterparty)
            if category_id in _HAS_REFERENCE:
                self.assertTrue(ledger.reference)
            else:
                self.assertIsNone(ledger.reference)
        self.assertEqual(seen, set(_TEMPLATE_ORDER))

    def test_amount_is_the_transaction_not_the_balance_or_limit(self):
        for _category_id, _json_kind, body in SAMPLES:
            result = classify_sms(body)
            ledger = result.ledger
            limit = re.search(r"AVAILABLE LIMIT IS (RS\. [\d,]+\.\d+)", body)
            if limit:
                self.assertNotEqual(ledger.amount_paisa, parse_amount_paisa(limit.group(1)))
                paid = re.search(r"PAYMENT OF (Rs\. [\d,]+\.\d+)", body)
                self.assertEqual(ledger.amount_paisa, parse_amount_paisa(paid.group(1)))
            if "Avl bal" in body:
                balance = re.search(r"Avl bal (INR [\d,]+\.\d+)", body)
                deposited = re.search(r"(INR [\d,]+\.\d+) deposited", body)
                self.assertNotEqual(ledger.amount_paisa, parse_amount_paisa(balance.group(1)))
                self.assertEqual(ledger.amount_paisa, parse_amount_paisa(deposited.group(1)))
            one_decimal = re.search(r"Spent (Rs\.\d+\.\d)(?!\d)", body)
            if one_decimal:
                self.assertEqual(ledger.amount_paisa, parse_amount_paisa(one_decimal.group(1)))
            labelled = re.search(r"(Txn Amt:INR[\d,]+\.\d+)", body)
            if labelled:
                self.assertEqual(ledger.amount_paisa, parse_amount_paisa(labelled.group(1)))
            inr_dot = re.search(r"(INR\.[\d,]+\.\d+)", body)
            if inr_dot:
                self.assertEqual(ledger.amount_paisa, parse_amount_paisa(inr_dot.group(1)))

    def test_apply_upserts_and_does_not_delete(self):
        by_id = {}
        for category_id, json_kind, body in SAMPLES:
            by_id.setdefault(category_id, (json_kind, body))

        when = datetime(2026, 10, 11, 8, 30, tzinfo=IST)
        conn = MagicMock()
        debit = classify_sms(by_id["upi_debit"][1])
        apply(conn, 7, debit.ledger, when)
        insert_sql, insert_params = conn.execute.call_args_list[0].args
        self.assertIn("ON CONFLICT (raw_sms_id) DO UPDATE", insert_sql)
        self.assertIn("updated_at = NOW()", insert_sql)
        self.assertNotIn("created_at", insert_sql.split("DO UPDATE", 1)[1])
        self.assertNotIn("raw_sms_data", insert_sql)
        self.assertEqual(insert_params[0], 7)
        self.assertEqual(insert_params[1], "debit")
        self.assertEqual(insert_params[2], debit.ledger.amount_paisa)
        self.assertEqual(insert_params[7], when)

        conn.reset_mock()
        ignored = classify_sms(by_id["card_otp"][1])
        self.assertIsNone(apply(conn, 8, ignored.ledger, when))
        conn.execute.assert_not_called()
        self.assertNotIn("XXXXXX", repr(ignored))

        conn.reset_mock()
        balance = classify_sms(by_id["balance_alert"][1])
        apply(conn, 9, balance.ledger, when)
        _sql, params = conn.execute.call_args_list[0].args
        self.assertEqual(params[1], "balance")
        self.assertEqual(params[2], 104090)
        self.assertEqual(params[3], "account")
        self.assertEqual(params[4], "XX3826")
        self.assertIsNone(params[5])
        self.assertIsNone(params[6])
        self.assertEqual(params[7], when)
        self.assertEqual(params[8], "balance_alert")

        conn.reset_mock()
        reminder = classify_sms(by_id["credit_card_statement"][1])
        apply(conn, 10, reminder.ledger, when)
        _sql, params = conn.execute.call_args_list[0].args
        self.assertEqual(params[1], "bill_reminder")
        self.assertIsNone(params[2])

    def test_csv_counts_match_categories_when_export_is_present(self):
        if not _CSV.is_file():
            self.skipTest("SMS export is not on disk")
        data = json.loads(_JSON.read_text(encoding="utf-8"))
        with _CSV.open(newline="", encoding="utf-8") as handle:
            bodies = [row["body"] for row in csv.DictReader(handle)]
        self.assertEqual(len(bodies), data["total"])
        counts = {category["id"]: 0 for category in data["categories"]}
        unmatched = []
        for body in bodies:
            result = classify_sms(body)
            if result.category_id is None:
                unmatched.append(_redact(body))
                continue
            self.assertIn(result.category_id, counts)
            counts[result.category_id] += 1
            ledger = result.ledger
            if result.processing_status == "ignored":
                self.assertIsNone(ledger)
                self.assertNotIn("XXXXXX", repr(result))
                continue
            if ledger is None:
                self.assertEqual(result.processing_status, "done")
                continue
            self.assertEqual(result.processing_status, "done")
            limit = re.search(r"AVAILABLE LIMIT IS (RS\. [\d,]+\.\d+)", body)
            if limit:
                self.assertNotEqual(ledger.amount_paisa, parse_amount_paisa(limit.group(1)))
            if "Avl bal" in body:
                balance = re.search(r"Avl bal (INR [\d,]+\.\d+)", body)
                deposited = re.search(r"(INR [\d,]+\.\d+) deposited", body)
                self.assertNotEqual(ledger.amount_paisa, parse_amount_paisa(balance.group(1)))
                self.assertEqual(ledger.amount_paisa, parse_amount_paisa(deposited.group(1)))
            one_decimal = re.search(r"Spent (Rs\.\d+\.\d)(?!\d)", body)
            if one_decimal:
                self.assertEqual(ledger.amount_paisa, parse_amount_paisa(one_decimal.group(1)))
        self.assertEqual(unmatched, [])
        for category in data["categories"]:
            self.assertEqual(counts[category["id"]], category["count"], category["id"])


if __name__ == "__main__":
    unittest.main()
