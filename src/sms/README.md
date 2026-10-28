# SMS decisions

Companion 2.0.4 drops OTP texts on the phone. Messages that still arrive are classified by the templates below into `transactions_sms`. `POST /sms/ingest_and_parse` inserts a new row in `raw_sms_data`, classifies, writes `transactions_sms` when the classification has a ledger, sets `processing_status`, then commits. A duplicate upload leaves both tables unchanged. `POST /sms/parse` reclassifies one stored raw SMS and updates that ledger row in place. `GET /sms/transactions` lists the ledger, including manual rows. Gmail `GET /transactions` does not include SMS.

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

`raw_sms_id` is `BIGINT UNIQUE REFERENCES raw_sms_data (id) ON DELETE CASCADE`, and null for a manual ledger row. One ledger row per raw SMS. Deleting the raw row deletes its ledger row. A manual row has no raw SMS to delete.

Columns: `kind` (`debit`, `credit`, `bill_reminder`, or `balance`), `amount_paisa`, `instrument`, `account_mask`, `counterparty`, `reference`, `sms_received_at`, `template_name`, plus `id`, `created_at`, and `updated_at`. A bill reminder and a balance are not money spent. `template_name` is the category id from `samples/hdfc_categories.json`, or `manual` for a typed row. For an SMS ledger row, `sms_received_at` is copied from `raw_sms_data.received_at`. The parser does not read a date or a clock from the SMS body. `updated_at` is set by the write statement, and matches `created_at` on insert.

`amount_paisa` is null only for a reminder whose SMS has no amount (`credit_card_statement`). A debit, a credit, or a balance always has an amount. The check constraint matches that. Manual rows use the same rule. A balance stores the available amount, not money received or spent.

`POST /sms/transactions` inserts a manual ledger row and does not write `raw_sms_data`. `kind` is `debit`, `credit`, `bill_reminder`, or `balance`. `amount_paisa` is required except on a bill reminder. `sms_received_at` is the time the client sends, or `created_at` when the client omits it. `template_name` stays `manual`.

`PATCH /sms/transactions/{id}` may change `kind`, `amount_paisa`, `instrument`, `account_mask`, `counterparty`, `reference`, and `sms_received_at` on either kind of row. It sets `updated_at` to server time. It does not change `raw_sms_id`, `template_name`, or `created_at`.

`DELETE /sms/transactions/{id}` removes the ledger row only. The raw SMS keeps its processing status. A later `POST /sms/parse` of that raw id can insert a new SMS ledger row. A deleted manual row is not recreated.

`classify_sms` takes one raw body and returns the classification. It does not touch the database. The ledger module writes the ledger row. `processing_status` is set after that write: `done` when a ledger row is written or the message is info, `ignored` when an ignore rule matches, and `unmatched` when nothing matches. Neither step commits. `POST /sms/ingest_and_parse` does this for a new row in the same request. `POST /sms/parse` does it for one stored raw SMS. An existing SMS ledger row is updated in place (same `id` and `created_at`). Parser fields replace any hand edits, and `sms_received_at` is copied from the phone again. No ledger deletes that raw SMS's ledger row. There is no route that reclassifies every raw SMS.

JSON kind `reminder` is stored as `bill_reminder`. `balance_alert` is JSON kind `info` and is stored as `balance`. Other `ignore` and `info` categories write no ledger row. Categories with `count: 0` get no template until a real sample exists.

`parse_amount_paisa` in `src/sms/amount.py` runs on the amount span the template captured, not on the whole SMS, and not via `src/core/amount.py`. On a debit or a credit, an available balance or a credit limit in the same text is not the amount. On a balance alert, the captured amount is the available balance. If that span does not parse, the raw row is `unmatched` and later templates do not run.

`account_mask` is the account or card ending as the SMS writes it (`*3826`, `3826`, `XX3826`, `6517`, `x6517`).

Instruments: `upi` for a UPI send, receive, mandate debit, or e-mandate reminder; `credit_card` for card templates; `account` for salary and for a balance alert; `rd` for the recurring-deposit reminder. Card bill payments name no payer, so `counterparty` is null. The e-mandate reminder names no account, so `account_mask` is null. Salary `counterparty` is the ACH narration, and that template requires the letters `SALARY` in the narration. The deposited amount is the transaction. `Avl bal` is not.

A balance alert becomes a ledger row of kind `balance`: the available amount, the account mask as the SMS writes it, instrument `account`, and no counterparty or reference. The "as on" date stays in the raw SMS. Other info messages (reward points, login, password-reset complete, chat-banking registered, RM missed call, biometric on or off, card autopay switched on) do not become ledger rows. The password-reset SMS contains the word password and does not contain the new password. Reward points are points, not rupees. The balance figure is not a credit. A debit or credit that also quotes an available balance still records the movement. Ignore, and store no code: card OTP, netbanking OTP, chat-banking OTP, credit-card product OTP, and a declined card transaction. Those templates accept a 6-digit code or the redacted `XXXXXX`. The code is not a captured field.

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