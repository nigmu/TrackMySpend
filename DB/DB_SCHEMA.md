# Database schema — Smart Finance Tracker (SQLite)

## SQLite-wide conventions

| Convention | Detail |
|---|---|
| Primary keys | `INTEGER PRIMARY KEY` — SQLite auto-increments these |
| Datetimes | `TEXT` in ISO 8601 format: `YYYY-MM-DDTHH:MM:SS` |
| Booleans | `INTEGER` — `0` = false, `1` = true |
| JSON columns | `TEXT` — use SQLite's built-in `json_extract()` / `json_each()` for queries (requires SQLite ≥ 3.38) |
| Soft deletes | `is_deleted INTEGER DEFAULT 0` + `deleted_at TEXT` — never hard-delete user data |
| Foreign keys | Must run `PRAGMA foreign_keys = ON` at every new connection — SQLite does not enforce FKs by default |
| Amounts | Always stored as positive `REAL`; a separate `direction` column carries `'debit'` or `'credit'` |
| Secrets | OAuth tokens and API keys are stored **encrypted** in the DB; never plaintext |

---

## Domain map

```
Auth & user        →  users, app_settings
Ingestion          →  email_accounts, sms_sources, parse_jobs
Banking            →  bank_accounts, balance_snapshots, credit_card_statements
Merchants          →  merchants, categories, tags
Transactions       →  transactions, transaction_tags, transaction_attachments
Splits             →  splits, split_participants, split_settlements, split_reminders
Income & planning  →  income_sources, salary_config, holidays, budgets,
                      recurring_transactions, planned_expenses
Alerts             →  notifications
Logs               →  system_logs
```

Total: **25 tables**

---

## 1. Auth & user

### `users`
Single-user system. Only one row will ever exist.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | Auto-increment |
| username | TEXT | NOT NULL, UNIQUE | |
| password_hash | TEXT | NOT NULL | bcrypt hash |
| pin_hash | TEXT | | Optional short PIN for quick re-lock |
| session_timeout_min | INTEGER | | Default `30` |
| created_at | TEXT | NOT NULL | |
| last_login_at | TEXT | | |

---

### `app_settings`
Key-value store for all configurable application settings.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| key | TEXT | NOT NULL, UNIQUE | e.g. `log_retention_days`, `default_currency`, `llm_model`, `anomaly_threshold_multiplier` |
| value | TEXT | NOT NULL | Stored as string; cast in application layer |
| description | TEXT | | Human-readable description of the setting |
| updated_at | TEXT | | |

Seed values on first run:

| key | default value |
|---|---|
| `default_currency` | `INR` |
| `log_retention_days` | `365` |
| `llm_model` | `gpt-4o` |
| `anomaly_threshold_multiplier` | `3` |
| `salary_alert_grace_days` | `1` |
| `budget_alert_threshold_pct` | `80` |

---

## 2. Ingestion

### `email_accounts`
Gmail accounts connected via OAuth for email parsing.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| user_id | INTEGER | FK → users.id, NOT NULL | |
| email_address | TEXT | NOT NULL, UNIQUE | |
| oauth_access_token | TEXT | NOT NULL | Encrypted at rest |
| oauth_refresh_token | TEXT | NOT NULL | Encrypted at rest |
| polling_interval_min | INTEGER | | Default `60` |
| last_polled_at | TEXT | | |
| is_active | INTEGER | | Default `1` |
| created_at | TEXT | NOT NULL | |

---

### `sms_sources`
Phone numbers registered for SMS-based transaction parsing (optional feature).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| user_id | INTEGER | FK → users.id, NOT NULL | |
| phone_number | TEXT | NOT NULL, UNIQUE | |
| carrier | TEXT | | e.g. `Airtel`, `Jio` |
| is_active | INTEGER | | Default `1` |
| last_parsed_at | TEXT | | |
| created_at | TEXT | NOT NULL | |

---

### `parse_jobs`
One row per parse attempt — email, SMS, CSV/PDF import, or manual backfill. Acts as an operational log for the ingestion pipeline.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| email_account_id | INTEGER | FK → email_accounts.id | Nullable; set for email source |
| sms_source_id | INTEGER | FK → sms_sources.id | Nullable; set for SMS source |
| source_type | TEXT | NOT NULL | `'email'` \| `'sms'` \| `'import'` \| `'backfill'` |
| status | TEXT | NOT NULL | `'pending'` \| `'running'` \| `'success'` \| `'failed'` |
| input_preview | TEXT | | First 500 chars of raw input for debugging |
| llm_input | TEXT | | Full prompt sent to LLM |
| llm_output | TEXT | | Raw LLM response |
| transactions_extracted | INTEGER | | Count; default `0` |
| error_message | TEXT | | Populated on failure; surfaced visibly in UI |
| started_at | TEXT | | |
| completed_at | TEXT | | |

---

## 3. Banking

### `bank_accounts`
Each bank account or credit card owned by the user.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| user_id | INTEGER | FK → users.id, NOT NULL | |
| display_name | TEXT | NOT NULL | e.g. `HDFC Savings`, `Axis Credit Card` |
| account_type | TEXT | NOT NULL | `'savings'` \| `'current'` \| `'credit_card'` \| `'wallet'` |
| bank_name | TEXT | | |
| account_number_masked | TEXT | | Last 4 digits only |
| credit_limit | REAL | | Credit cards only |
| billing_cycle_day | INTEGER | | Credit cards: statement generation day of month |
| due_day | INTEGER | | Credit cards: payment due day of month |
| current_balance | REAL | | Manually updated snapshot |
| balance_updated_at | TEXT | | |
| is_active | INTEGER | | Default `1` |
| created_at | TEXT | NOT NULL | |

---

### `balance_snapshots`
Periodic balance history per account — enables net worth trend tracking over time.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| bank_account_id | INTEGER | FK → bank_accounts.id, NOT NULL | |
| balance | REAL | NOT NULL | Balance at snapshot time |
| snapshot_date | TEXT | NOT NULL | ISO date `YYYY-MM-DD` |
| source | TEXT | | `'manual'` \| `'auto'` (auto = recorded when a transaction is parsed) |
| created_at | TEXT | NOT NULL | |

Index: `(bank_account_id, snapshot_date)`

---

### `credit_card_statements`
One row per monthly credit card statement cycle.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| bank_account_id | INTEGER | FK → bank_accounts.id, NOT NULL | Must be `account_type = 'credit_card'` |
| statement_date | TEXT | NOT NULL | Date statement was generated |
| due_date | TEXT | NOT NULL | Payment due date |
| total_due | REAL | NOT NULL | Full outstanding amount |
| min_due | REAL | | Minimum payment amount |
| paid_amount | REAL | | Default `0` |
| paid_at | TEXT | | Date payment was received |
| status | TEXT | NOT NULL | `'unpaid'` \| `'partial'` \| `'paid'` \| `'overdue'` |
| created_at | TEXT | NOT NULL | |

---

## 4. Merchants & categories

### `categories`
Spending and income categories. Supports one level of sub-categories via `parent_id`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL | e.g. `Food`, `Health`, `Salary` |
| parent_id | INTEGER | FK → categories.id | Self-referential; `NULL` = top-level |
| color | TEXT | | Hex color string for UI rendering |
| icon | TEXT | | Icon identifier |
| is_system | INTEGER | | `1` = pre-loaded default, `0` = user-created |
| is_active | INTEGER | | Soft-delete via `0` |
| created_at | TEXT | NOT NULL | |

Pre-loaded system categories: `Food`, `Transport`, `Health`, `Utilities`, `Entertainment`, `Shopping`, `Investment`, `EMI / Loan`, `Salary`, `Transfers`, `Miscellaneous`.

---

### `merchants`
Shops, people, services — identified by their UPI IDs, VPAs, or account numbers.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| display_name | TEXT | NOT NULL | e.g. `Blinkit`, `Rohit Sharma` |
| canonical_name | TEXT | | Lowercased, normalised version for deduplication |
| identifiers | TEXT | | JSON array of UPI IDs, account numbers, VPAs — e.g. `["rohit@upi", "9876543210"]` |
| default_category_id | INTEGER | FK → categories.id | Used when transaction-level category is not determinable |
| alias | TEXT | | User-given nickname |
| notes | TEXT | | Free-text profile notes; persists long-term |
| is_verified | INTEGER | | `0` = auto-detected by parser, `1` = manually confirmed by user |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | | |

> Note: `identifiers` is stored as a JSON text column. Use `json_each(identifiers)` to query individual identifiers. A single merchant can have multiple UPI IDs and account numbers.

---

### `tags`
Free-form labels that cross-cut categories for event-based grouping.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL, UNIQUE | e.g. `goa-trip`, `birthday-party`, `office-team-lunch` |
| created_at | TEXT | NOT NULL | |

---

## 5. Transactions

### `transactions`
Core table. Every debit and credit across all accounts and sources.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| user_id | INTEGER | FK → users.id, NOT NULL | |
| bank_account_id | INTEGER | FK → bank_accounts.id, NOT NULL | |
| merchant_id | INTEGER | FK → merchants.id | Nullable; resolved by parser or manually |
| category_id | INTEGER | FK → categories.id | Nullable; overrides merchant default when set |
| income_source_id | INTEGER | FK → income_sources.id | Nullable; set when this credit matches an expected income |
| amount | REAL | NOT NULL | Always positive |
| direction | TEXT | NOT NULL | `'debit'` \| `'credit'` |
| txn_type | TEXT | | `'upi'` \| `'neft'` \| `'imps'` \| `'rtgs'` \| `'cash'` \| `'emi'` \| `'credit_card'` \| `'transfer'` |
| description | TEXT | | Raw text extracted from email or SMS |
| notes | TEXT | | User-written annotation (natural language → LLM classified) |
| txn_date | TEXT | NOT NULL | Actual transaction date |
| value_date | TEXT | | Settlement / value date |
| reference_number | TEXT | | Bank reference or UTR number |
| balance_after | REAL | | Account balance after this transaction (from email) |
| source | TEXT | NOT NULL | `'email'` \| `'sms'` \| `'manual'` \| `'import'` |
| parse_job_id | INTEGER | FK → parse_jobs.id | Nullable; links to the ingestion job that created this row |
| is_transfer | INTEGER | | `1` = movement between own accounts; excluded from P&L |
| is_deleted | INTEGER | | Soft delete; default `0` |
| deleted_at | TEXT | | |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | | |

Recommended indexes:
- `(bank_account_id, txn_date)`
- `(merchant_id)`
- `(category_id)`
- `(direction, txn_date)`

---

### `transaction_tags`
Many-to-many junction between transactions and tags.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| transaction_id | INTEGER | PK, FK → transactions.id | |
| tag_id | INTEGER | PK, FK → tags.id | |

Composite primary key: `(transaction_id, tag_id)`

---

### `transaction_attachments`
Receipt photos or documents attached to a transaction.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| transaction_id | INTEGER | FK → transactions.id, NOT NULL | |
| file_path | TEXT | NOT NULL | Relative path on disk |
| file_type | TEXT | | `'image'` \| `'pdf'` \| `'other'` |
| created_at | TEXT | NOT NULL | |

---

## 6. Splits

### `splits`
A split bucket attached to a parent transaction where the user paid on behalf of others.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| parent_txn_id | INTEGER | FK → transactions.id, NOT NULL | The original debit transaction |
| total_amount | REAL | NOT NULL | Full amount paid |
| user_share | REAL | NOT NULL | What the user actually owes after deducting others' shares |
| notes | TEXT | | e.g. `Goa hotel split` |
| status | TEXT | NOT NULL | `'open'` \| `'partial'` \| `'settled'` |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | | |

Constraint: `user_share <= total_amount`
Constraint: `user_share = total_amount - SUM(split_participants.owed_amount)` (enforced in application layer)

---

### `split_participants`
One row per person who owes money in a split.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| split_id | INTEGER | FK → splits.id, NOT NULL | |
| person_name | TEXT | NOT NULL | |
| merchant_id | INTEGER | FK → merchants.id | Nullable; set if this person has a known UPI ID |
| owed_amount | REAL | NOT NULL | How much this person owes |
| paid_amount | REAL | | Running total received; default `0` |
| status | TEXT | NOT NULL | `'pending'` \| `'partial'` \| `'settled'` |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | | |

---

### `split_settlements`
Each incoming payment transaction that clears part or all of a participant's share.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| split_participant_id | INTEGER | FK → split_participants.id, NOT NULL | |
| transaction_id | INTEGER | FK → transactions.id, NOT NULL | The incoming credit transaction |
| amount | REAL | NOT NULL | Amount applied toward this settlement |
| settled_at | TEXT | NOT NULL | |
| notes | TEXT | | |

---

### `split_reminders`
Tracks when a payment reminder was last sent to a participant.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| split_participant_id | INTEGER | FK → split_participants.id, NOT NULL | |
| reminded_at | TEXT | NOT NULL | Timestamp when reminder was generated |
| channel | TEXT | | `'whatsapp_draft'` \| `'text_draft'` \| `'in_app'` |
| message_preview | TEXT | | First 200 chars of generated message |

---

## 7. Income & planning

### `income_sources`
Salary, freelance, rent, dividends — each tracked independently with its own expected schedule.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL | e.g. `Primary salary`, `Freelance — Client X` |
| type | TEXT | NOT NULL | `'salary'` \| `'freelance'` \| `'rental'` \| `'dividend'` \| `'other'` |
| expected_amount | REAL | | Expected monthly/periodic amount |
| bank_account_id | INTEGER | FK → bank_accounts.id | Nullable; which account receives this income |
| expected_day_type | TEXT | | `'last_working_day'` \| `'fixed_date'` \| `'manual'` |
| expected_date | INTEGER | | Day of month if `fixed_date` |
| is_active | INTEGER | | Default `1` |
| created_at | TEXT | NOT NULL | |

---

### `salary_config`
Last-working-day calculation rules for a salary income source.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| income_source_id | INTEGER | FK → income_sources.id, NOT NULL, UNIQUE | One config per income source |
| working_days | TEXT | | JSON array of weekday numbers; e.g. `[1,2,3,4,5]` = Mon–Fri |
| last_day_override | TEXT | | Manual override for the next pay date specifically |
| updated_at | TEXT | | |

---

### `holidays`
Public and custom holidays used to calculate the last working day of each month.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| date | TEXT | NOT NULL, UNIQUE | `YYYY-MM-DD` |
| name | TEXT | NOT NULL | e.g. `Diwali`, `Republic Day` |
| created_at | TEXT | NOT NULL | |

---

### `budgets`
Spending limits per category per period, with configurable alert thresholds.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| category_id | INTEGER | FK → categories.id, NOT NULL | |
| period_type | TEXT | NOT NULL | `'monthly'` \| `'quarterly'` \| `'yearly'` |
| amount | REAL | NOT NULL | Budget limit in INR |
| alert_threshold_pct | INTEGER | | Alert fires at this % of budget; default `80` |
| is_active | INTEGER | | Default `1` |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | | |

---

### `recurring_transactions`
Auto-detected or manually registered recurring debits — subscriptions, EMIs, rent, utility bills.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| merchant_id | INTEGER | FK → merchants.id | Nullable |
| category_id | INTEGER | FK → categories.id | Nullable |
| label | TEXT | | e.g. `Netflix subscription`, `Home loan EMI` |
| expected_amount | REAL | | |
| amount_tolerance_pct | INTEGER | | Fuzzy match tolerance; default `5` |
| frequency | TEXT | NOT NULL | `'weekly'` \| `'monthly'` \| `'quarterly'` \| `'yearly'` |
| expected_day | INTEGER | | Day of month the charge typically appears |
| last_seen_at | TEXT | | Date of most recent matching transaction |
| next_expected_at | TEXT | | Computed expected next occurrence |
| auto_detected | INTEGER | | `1` = system identified it, `0` = manually added |
| is_active | INTEGER | | Default `1` |
| created_at | TEXT | NOT NULL | |

---

### `planned_expenses`
Future big purchases tracked so they can be factored into forward-looking budget projections.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| title | TEXT | NOT NULL | e.g. `New laptop` |
| amount | REAL | NOT NULL | Estimated cost |
| expected_date | TEXT | | Target purchase date |
| category_id | INTEGER | FK → categories.id | Nullable |
| notes | TEXT | | |
| is_fulfilled | INTEGER | | Default `0` |
| linked_txn_id | INTEGER | FK → transactions.id | Nullable; set when the actual purchase is recorded |
| created_at | TEXT | NOT NULL | |

---

## 8. Alerts

### `notifications`
Stores all system-generated alerts. Tracks shown/dismissed state so alerts are not repeated.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| type | TEXT | NOT NULL | `'budget_alert'` \| `'salary_not_received'` \| `'cc_due_soon'` \| `'cc_overdue'` \| `'anomaly'` \| `'recurring_missed'` \| `'parse_failure'` |
| title | TEXT | NOT NULL | Short alert title for UI |
| body | TEXT | | Full alert message |
| entity_type | TEXT | | e.g. `'budget'`, `'bank_account'`, `'transaction'` |
| entity_id | INTEGER | | FK to the related row (not a hard FK — polymorphic) |
| is_read | INTEGER | | Default `0` |
| is_dismissed | INTEGER | | Default `0` |
| created_at | TEXT | NOT NULL | |
| read_at | TEXT | | |
| dismissed_at | TEXT | | |

---

## 9. Logs

### `system_logs`
Immutable audit trail for every action in the system. Never updated or deleted (retention controlled by `app_settings.log_retention_days`).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| level | TEXT | NOT NULL | `'info'` \| `'warn'` \| `'error'` \| `'debug'` |
| action_type | TEXT | NOT NULL | e.g. `LOGIN`, `LOGOUT`, `PARSE_EMAIL_START`, `PARSE_EMAIL_SUCCESS`, `CREATE_TXN`, `UPDATE_TXN`, `DELETE_TXN`, `CREATE_SPLIT`, `UPDATE_CATEGORY`, `BUDGET_ALERT_FIRED` |
| entity_type | TEXT | | e.g. `'transaction'`, `'merchant'`, `'split'`; nullable |
| entity_id | INTEGER | | FK to the affected row; nullable |
| old_value | TEXT | | JSON snapshot of the row before a change |
| new_value | TEXT | | JSON snapshot of the row after a change |
| ip_address | TEXT | | |
| user_agent | TEXT | | |
| created_at | TEXT | NOT NULL | |

Recommended index: `(action_type, created_at)`, `(entity_type, entity_id)`

---

## Key relationships summary

```
users
  ├── email_accounts
  ├── sms_sources
  ├── bank_accounts
  │     ├── balance_snapshots
  │     └── credit_card_statements
  ├── income_sources
  │     └── salary_config
  └── (all other tables via user_id or transitively)

transactions  (central table)
  ├── bank_accounts
  ├── merchants
  ├── categories
  ├── income_sources          ← links salary credits back to income source
  ├── parse_jobs              ← which ingestion job created this row
  ├── transaction_tags ──── tags
  ├── transaction_attachments
  ├── splits
  │     └── split_participants
  │           ├── split_settlements ── transactions (the repayment credits)
  │           └── split_reminders
  └── planned_expenses (linked_txn_id)

merchants
  ├── categories (default_category_id)
  └── split_participants (when participant has known UPI)

budgets ── categories
recurring_transactions ── merchants, categories
notifications  (polymorphic entity_type / entity_id)
system_logs    (polymorphic entity_type / entity_id)
app_settings   (standalone key-value)
holidays       (standalone; referenced in application layer for salary calc)
```

---

## Schema change log

| Version | Change |
|---|---|
| v1.0 | Initial 19-table design |
| v1.1 | Added `notifications`, `balance_snapshots`, `credit_card_statements`, `sms_sources`, `split_reminders`, `app_settings` (6 new tables); added `income_source_id` FK to `transactions`; added `sms_source_id` FK to `parse_jobs` |
