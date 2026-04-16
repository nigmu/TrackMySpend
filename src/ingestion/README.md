# Ingestion Module (Gmail Fetch + Polling)

This folder is responsible for pulling Gmail message data into the TrackMySpend
pipeline and placing parser-ready rows into the first staging table.

It does not decide parsing rules for stage 2. That responsibility now lives in
the parsing layer.

---

## What This Folder Does

At a high level, ingestion:

1. Reads connected Gmail accounts from `email_accounts`.
2. Builds Google credentials from encrypted DB tokens.
3. Fetches Gmail messages in two modes:
   - `top-n` snapshot fetch
   - incremental `historyId`-based fetch
4. Stores filtered fetch output in `ingestion_parser_staging`.
5. Updates mailbox sync markers in `email_accounts`:
   - `last_polled_at`
   - `last_history_id`
6. Exposes ingestion HTTP endpoints for manual fetch and sync.

It intentionally does not:

- apply parser keyword rules
- move rows into `parsing_sender_regex_staging`
- interpret parser statuses beyond writing raw stage-1 input

---

## Current File Roles

### `ingest.py`

- Exposes the ingestion router for app wiring.

### `email_fetcher.py`

- Handles Gmail API access only.
- Builds credentials from encrypted tokens.
- Fetches:
  - top-N raw messages
  - top-N filtered messages
  - incremental filtered messages using `last_history_id`

Important note:

- Filtered fetch responses currently keep lightweight fields such as
  `from`, `to`, `subject`, `date_header`, timestamps, and Gmail `snippet`.
- Full message payload still exists in raw responses and the staged row keeps the
  entire message snapshot in `raw_json`.
- `snippet` is only Gmail preview text and may be truncated.

### `poller.py`

- Decides when an account is due for polling.
- Runs incremental sync for one or all active accounts.
- Writes fetched filtered rows into `ingestion_parser_staging` by calling
  `staging_store.store_for_parser(...)`.
- Updates:
  - `last_history_id`
  - `last_polled_at`

### `staging_store.py`

- Accepts filtered messages from poller.
- Inserts them into `ingestion_parser_staging`.
- Uses idempotent insert semantics with the unique constraint on
  `(email_account_id, gmail_message_id)`.
- Supports `keep_existing`:
  - `True` -> append/dedupe
  - `False` -> clear stage-1 table before insert

### `routes.py`

- HTTP wrapper for ingestion fetch/sync functions.
- Keeps validation and response shaping separate from business logic.

---

## Core Design Decisions

## 1) Two fetch models exist on purpose

### Top-N fetch

Best for:

- bootstrap
- diagnostics
- quick inspection of latest mailbox contents

Examples:

- `GET /ingestion/accounts/{id}/messages/raw/top-n?top_n=10`
- `GET /ingestion/accounts/{id}/messages/filtered/top-n?top_n=10`

### Incremental fetch

Best for:

- ongoing sync
- lower Gmail API cost
- production-style polling

Relies on:

- `email_accounts.last_history_id`

Why both:

- top-N is simple but wasteful for repeated runs
- incremental is efficient but needs bootstrap and debugging support

---

## 2) Polling and staging are separate concerns

- `poller.py` decides when sync runs.
- `staging_store.py` decides how fetched rows are persisted.

This keeps:

- fetch timing logic independent
- insert/dedupe behavior reusable
- parser stage-1 storage explicit and testable

---

## 3) Ingestion owns only stage 1

The ingestion layer writes to:

- `ingestion_parser_staging`

The parsing layer owns:

- filtering rows from stage 1 into stage 2
- maintaining keyword rules
- writing to `parsing_sender_regex_staging`

This is an intentional boundary:

- ingestion fetches and stages raw parser input
- parsing decides which staged rows are relevant for downstream parsing

---

## 4) Stage-1 status drives parser pickup

`ingestion_parser_staging` includes `stage2_status`.

Current meaning:

- `NULL` -> not yet evaluated by stage-2 parser filter
- `done` -> row was considered and moved to stage 2
- `skipped` -> row was considered and rejected by stage-2 filter

The parsing layer reads stage-1 rows using:

- `WHERE stage2_status IS NULL`
- `ORDER BY id ASC`
- `LIMIT ?`

To keep that fast, schema includes:

- index on `(stage2_status, id)`

This gives a safe queue-like scan without relying on a fragile
`last_processed_id` checkpoint.

---

## End-to-End Flow

### A) Manual filtered top-N read

1. API call:
   - `GET /ingestion/accounts/1/messages/filtered/top-n?top_n=5`
2. Route calls:
   - `fetch_top_n_filtered_messages_for_one_account(1, 5)`
3. Fetcher returns filtered message dicts.
4. No staging row is written automatically in this path.
5. No sync marker is updated.

### B) Manual incremental sync for one account

1. API call:
   - `GET /ingestion/accounts/1/messages/filtered/latest`
2. Route calls:
   - `sync_latest_filtered_messages_for_one_account(1)`
3. Poller:
   - fetches incremental filtered messages
   - stores them in `ingestion_parser_staging`
   - updates `last_history_id`
   - updates `last_polled_at`
4. Response includes fetched messages plus `staged_for_parser`.

### C) Background poll loop

1. `run_poller_loop()` wakes every ~30 seconds.
2. Loads active accounts.
3. Filters accounts due by `polling_interval_min`.
4. Runs incremental sync for due accounts.
5. Stages fetched rows and updates sync markers.
6. Sleeps again.

### D) Parser stage-2 handoff

1. Parsing reads from `ingestion_parser_staging`.
2. It only scans rows with `stage2_status IS NULL`.
3. If parser keyword rules pass:
   - row is inserted into `parsing_sender_regex_staging`
   - source row becomes `stage2_status = 'done'`
4. If parser keyword rules fail:
   - source row becomes `stage2_status = 'skipped'`

---

## Stage-1 Table Contract

### `ingestion_parser_staging`

Purpose:

- transient parser-input staging table populated by ingestion

Owner:

- written by ingestion
- consumed by parsing

Key fields:

- identity:
  - `email_account_id`
  - `gmail_message_id`
- headers/meta:
  - `from_header`
  - `to_header`
  - `subject`
  - `date_header`
  - `internal_date_ms`
  - `gmail_received_at_utc`
  - `date_header_iso`
- text:
  - `snippet`
- audit/debug:
  - `fetched_at`
  - `raw_json`
- parser handoff state:
  - `stage2_status`

Rules:

- deduped by unique constraint on `(email_account_id, gmail_message_id)`
- stage-1 should be treated as parser input, not as final parsed output
- `raw_json` is the source-of-truth snapshot if parser later needs richer payload

---

## Current API Surface

Base prefix: `/ingestion`

- `GET /accounts/{account_id}/messages/raw/top-n?top_n=10`
  - returns top N raw Gmail messages

- `GET /accounts/{account_id}/messages/filtered/top-n?top_n=10`
  - returns top N filtered messages

- `GET /accounts/{account_id}/messages/filtered/latest`
  - runs incremental sync for one account
  - stages fetched rows into `ingestion_parser_staging`

- `GET /accounts/messages/filtered/latest`
  - runs incremental sync for all active accounts
  - stages fetched rows into `ingestion_parser_staging`

---

## Current Parsing Dependency

The current parsing layer depends on these ingestion decisions:

- keywords for stage-2 filter live in `src/global_configs.py`
- stage-2 parser route lives under `/parsing`
- ingestion does not know or care which keywords pass
- ingestion only provides stage-1 rows plus status-neutral payload

---

## Error and Edge Cases

- Account missing -> `not_found` / HTTP 404
- Account inactive -> `inactive` / HTTP 400 or empty fetch depending on path
- Empty mailbox -> empty list, not an error
- First incremental run without `last_history_id`:
  - establishes checkpoint
  - may return zero messages while still storing new history position
- Gmail `snippet` may be truncated:
  - use `raw_json` if downstream parsing later needs fuller message content

---

## Why This Structure Works

- Clear ownership:
  - ingestion fetches and stages
  - parsing filters and advances rows
- Supports both manual debugging and automated sync
- Keeps Gmail fetch logic reusable
- Keeps stage-1 durable enough for parser retries without overcomplicating ingestion
- Uses status-based queue scanning plus `(stage2_status, id)` index for scalable stage-2 pickup
