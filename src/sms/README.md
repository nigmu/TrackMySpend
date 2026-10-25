# SMS decisions

Companion 2.0.4 drops OTP texts on the phone. Messages that still arrive are classified by the templates below into `transactions_sms`. `POST /sms/ingest_and_parse` inserts a new row in `raw_sms_data`, classifies, writes `transactions_sms` when the classification has a ledger, sets `processing_status`, then commits. A duplicate upload leaves both tables unchanged. **Parse all** on the SMS page calls `POST /sms/parse_all`, reclassifies every raw row, deletes and rewrites that row's ledger, and returns `total`, `done`, `ignored`, `unmatched`. `GET /sms/transactions` lists the ledger. Gmail `GET /transactions` does not include SMS.

## Where a message goes

The phone sender filter still runs first (`HDFCBK` and the other patterns on the device). Then:

1. An OTP text becomes a Log row whose body is the fixed text `OTP ignored`. The SMS is not written to the outbox, the JSON export, or the server. Status is `ignored`. It is not uploaded, not retried, and not counted as pending or failed. Live receive and inbox backfill both do this, after the sender filter and before `insertIfNew`.
2. Anything else is queued and uploaded as before.

The phone Messages app still keeps the original SMS. Rows already stored in the outbox or in `raw_sms_data` are left as they are.

## What counts as an OTP

`OTP_CODE_LENGTH` is `6`, a constant in `OtpFilter`. A message is an OTP only when both are true:

- The body contains `OTP`, any case.
- It contains a run of exactly 6 digits that is not part of a longer number, and `Rs` or `INR` is not directly in front of that run.

`Rs` and `INR` match any case, with an optional dot and an optional space: `Rs.100000`, `Rs. 100000`, `Rs 100000`, `Rs100000`, `INR 100000`, `INR.100000`, `INR100000`. Commas are not required for a number to be an amount.

Kept:

- `Spent Rs.61.71 On HDFC Bank Card...` has no `OTP`.
- `Rs.299 without OTP/PIN` says `OTP` and has no 6-digit run.
- `Rs.100000 without OTP/PIN` says `OTP`, and `100000` is an amount.

Dropped:

- `OTP is 492045 for txn of INR 61.71...` The amount does not save it.
- `OTP is 492045 for txn of INR 100000`. `100000` is ignored. `492045` is still a code.

A 12-digit UPI ref, an 11-digit phone number, and a 4-digit card ending are not 6-digit runs. `026101` is a code.

PIN and password alerts are not filtered on the phone. This export has change notices (`IPIN (Password) reset is complete`, `Continue using UPI PIN`) and no SMS that contains a PIN or a password. Declined and failed messages are not filtered on the phone either.

## transactions_sms

Mail `transactions` stays mail-only. Parsed SMS rows go to `transactions_sms`.

`raw_sms_id` is `BIGINT NOT NULL UNIQUE REFERENCES raw_sms_data (id) ON DELETE CASCADE`. One ledger row per SMS. Deleting the raw row deletes the ledger row.

Columns: `kind` (`debit`, `credit`, or `bill_reminder`), `amount_paisa`, `instrument`, `account_mask`, `counterparty`, `reference`, `sms_received_at`, `template_name`, plus `id` and `created_at`. `kind` keeps a reminder out of spend totals. `template_name` is the category id from `samples/hdfc_categories.json`. `sms_received_at` is copied from `raw_sms_data.received_at` when the ledger row is written. The parser does not read a date or a clock from the SMS body.

`amount_paisa` is null only for a reminder whose SMS has no amount (`credit_card_statement`). A debit or a credit always has an amount. The check constraint matches that.

`classify_sms` takes one raw body and returns the classification. `apply_sms_classification` writes it: `processing_status` becomes `done` when a ledger row is inserted or the message is info, `ignored` when an ignore rule matches, and `unmatched` when nothing matches. Neither function commits. `POST /sms/ingest_and_parse` calls them for a new row in the same request. `POST /sms/parse_all` deletes that row's ledger, then calls them again for every raw row.

JSON kind `reminder` is stored as `bill_reminder`. JSON kinds `ignore` and `info` write no ledger row. Categories with `count: 0` get no template until a real sample exists.

`parse_amount_paisa` in `src/sms/amount.py` runs on the amount span the template captured, not on the whole SMS, and not via `src/core/amount.py`. An available balance or credit limit is not the transaction. If that span does not parse, the raw row is `unmatched` and later templates do not run.

`account_mask` is the account or card ending as the SMS writes it (`*3826`, `3826`, `XX3826`, `6517`, `x6517`).

Instruments: `upi` for a UPI send, receive, mandate debit, or e-mandate reminder; `credit_card` for card templates; `account` for salary; `rd` for the recurring-deposit reminder. Card bill payments name no payer, so `counterparty` is null. The e-mandate reminder names no account, so `account_mask` is null. Salary `counterparty` is the ACH narration, and that template requires the letters `SALARY` in the narration. The deposited amount is the transaction. `Avl bal` is not.

Info messages (balance alert, reward points, login, password-reset complete, chat-banking registered, RM missed call, biometric on or off, card autopay switched on) do not become ledger rows. The password-reset SMS contains the word password and does not contain the new password. Reward points are points, not rupees. The balance figure is not a credit. Ignore, and store no code: card OTP, netbanking OTP, chat-banking OTP, credit-card product OTP, and a declined card transaction. Those templates accept a 6-digit code or the redacted `XXXXXX`. The code is not a captured field.

## Template order

The parser walks this list and stops at the first match. It does not score templates. Specific wording stands before general wording:

1. `card_otp`
2. `netbanking_otp`
3. `chat_banking_otp`
4. `credit_card_product_otp`
5. `credit_card_declined`
6. `balance_alert`
7. `login_alert`
8. `netbanking_password_reset`
9. `chat_banking_registered`
10. `reward_points`
11. `rm_call`
12. `upi_biometric_disabled`
13. `upi_biometric_enabled`
14. `credit_card_autopay_active`
15. `credit_card_upi_txn` (`Txn Rs` … `by UPI`, before card spend)
16. `credit_card_spend` (`Spent Rs`)
17. `credit_card_contactless_debit`
18. `credit_card_emandate_success`
19. `credit_card_autopay_upcoming`
20. `credit_card_refund`
21. `credit_card_payment_received` (all-caps, includes available limit)
22. `credit_card_online_payment` (before the sentence-case payment)
23. `credit_card_payment_credited`
24. `upi_mandate_debit` (before a generic UPI send)
25. `upi_debit`
26. `upi_credit`
27. `emandate_upcoming`
28. `salary_credit`
29. `rd_installment_due`
30. `credit_card_statement`

Check: `python -m unittest src.sms.test_hdfc -v`. The export count check skips when `samples/` is not on disk.