"""Small tester for the basic transaction parser.

Run with: python -m src.parsing.tests.test_basic
"""

from ..basic import parse_text


_SAMPLES = [
    ("Dear Customer, Rs. 240.00 is successfully credited to your account **1111 by VPA demo.payer.sample@okaxis SAMPLE PERSON NAME on 18-04-26. Your UPI transaction reference number is 900000000001. Thank you for banking with us. Warm Regards, HDFC Bank", "credit"),
    ("Dear Customer, Greetings from HDFC Bank!  Transaction reversal of Rs.14.35 has been initiated to your HDFC Bank Credit Card ending 2222.  From Merchant:SAMPLE RIDESHARE INDIA PVT L Date Time: 09 Dec, 2025 at 12:55:40  Please allow up to 48 hours for the reversal to reflect in your card statement.  Thank you for banking with us.  Warm regards, HDFC Bank  This is a system-generated email. Please do not reply. ", "reversal"),
    ("INR 500 is successfully credited to your account", "credit"),
    ("You spent Rs. 240 at STORE", "debit"),
    ("Dear Customer, Rs.28.50 has been debited from account 1111 to VPA metro.sample.demo@hdfcbank DEMO METRO TRANSIT on 18-04-26. Your UPI transaction reference number is 900000000002. If you did not authorize this transaction, please report it immediately by calling 18002586161 Or SMS BLOCK UPI to 7308080808. Warm Regards, HDFC Bank", "debit"),
    ("Dear Customer, Greetings from HDFC Bank!  Rs.120.00 is debited from your HDFC Bank Debit Card ending 3333 at SAMPLE HYPERMARKET on 26 Mar, 2026 at 18:18:21.", "debit"),
    ("Dear Customer, Rs.214.00 has been debited from your HDFC Bank RuPay Credit Card XX4444 to foodorder.demo@payment SAMPLE FOOD APP on 29-03-26.", "debit"),
    ("Dear Customer, Rs. 259.00 has been debited from your HDFC Bank Credit Card ending 4444 towards SAMPLE BRAND PRIVATE on 18 Apr, 2026 at 13:38:32.", "debit"),
    ("Monthly statement is ready", "debit"),
]


def run_tests() -> None:
    for text, expected in _SAMPLES:
        result = parse_text(text)
        print(result)
    print("All basic parser samples ran.")


if __name__ == "__main__":
    run_tests()
