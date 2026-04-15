# Ingestion Module (Gmail Fetch + Polling)

This folder is responsible for pulling raw Gmail message data into the TrackMySpend pipeline.
It is intentionally split into small modules so each layer has one job and can evolve
independently.

---

## What This Folder Does

At a high level, ingestion:

1. Reads connected Gmail accounts from `email_accounts`.
2. Builds Google credentials from encrypted DB tokens.
3. Fetches message data from Gmail API in two modes:
   - **Top-N fetch** (bootstrap / snapshot style)
   - **Incremental fetch** (historyId-based delta sync)
4. Updates sync markers in DB (`last_polled_at`, `last_history_id`).
5. Exposes API endpoints for manual fetch and manual polling triggers.

It does **not** parse transactions or normalize business data. That belongs to later
parsing/pipeline modules.

---

## File-by-File Architecture

### `ingest.py` (entry point)

- Exposes the ingestion router so `app.py` can mount it.
- Keeps app wiring simple and consistent with the auth module pattern.

Why this exists:
- Avoids importing internal route files directly from the app layer.
- Keeps folder encapsulation clean (`from .ingest import router`).

---

### `email_fetcher.py` (fetch business logic)

Contains Gmail API fetch logic only.

Main responsibilities:

- Build Google `Credentials` from encrypted tokens.
- Fetch top-N raw messages for an account.
- Fetch top-N filtered messages for an account.
- Fetch incremental messages based on `last_history_id`.

What it intentionally does **not** do:
- No polling cadence decisions.
- No automation loops.
- No schedule checks (`polling_interval_min`).

Why this separation:
- Fetching should be deterministic and reusable from both routes and poller.
- Scheduler concerns (when to fetch) should not be mixed with API client concerns
  (how to fetch).

---

### `poller.py` (automation + sync markers)

Contains polling mechanics and DB sync marker updates.

Main responsibilities:

- Manual one-shot polling functions (`poll_once_*`) for immediate sync.
- Incremental single-account poll helper.
- Automation loop (`run_poller_loop`) with interval gating.
- Marker updates:
  - `last_polled_at`
  - `last_history_id`

Why this separation:
- Polling orchestration is stateful/timing-based.
- Keeps route handlers thin and fetcher logic reusable.

---

### `routes.py` (HTTP layer)

Exposes ingestion endpoints and delegates to fetcher/poller functions.

Current endpoint families:

- Raw messages - one account - top N
- Filtered messages - one account - top N
- Filtered messages - one account - latest
- Filtered messages - all accounts - latest

Why this separation:
- HTTP concerns (query validation, response codes) stay in one file.
- Business logic is tested/reused without FastAPI request objects.

---

## Key Design Decisions and Why

## 1) Two fetch models: Top-N and Incremental

### Top-N
- Best for:
  - bootstrapping
  - debugging
  - “show me latest mailbox snapshot now”
- Endpoint examples:
  - `GET /ingestion/accounts/{id}/messages/raw/top-n?top_n=10`
  - `GET /ingestion/accounts/{id}/messages/filtered/top-n?top_n=10`

### Incremental (`historyId`)
- Best for:
  - ongoing sync with low API overhead
  - production-style background ingestion
- Relies on `email_accounts.last_history_id`.
- Only fetches changes since last known checkpoint.

Why both are required:
- Top-N alone is simple but wasteful for repeated syncs.
- Incremental alone is efficient but needs bootstrap and diagnostics support.

---

## 2) Manual polling ignores interval; loop respects interval

This is intentional:

- Manual/API-triggered polling should sync immediately (user intent = “do it now”).
- Background loop should obey `polling_interval_min` to avoid over-polling.

Outcome:
- You can force sync anytime.
- Automation remains controlled and cost-aware.

---

## 3) `last_polled_at` and `last_history_id` are separate markers

- `last_polled_at` answers: **when** did we last attempt sync?
- `last_history_id` answers: **from what mailbox checkpoint** should next incremental fetch start?

Why both:
- Scheduling and data checkpointing are different concerns.
- You need both for correct interval behavior and correct delta fetch behavior.

---

## 4) Raw endpoint and filtered endpoint both exist

- Raw endpoint returns payload-heavy data for diagnostics/future parser logic.
- Filtered endpoint returns essential UI/debug fields:
  - From, Subject, Date, snippet, normalized timestamps.

Why both:
- Different consumers (debuggers vs lightweight UI) need different payload shapes.

---

## End-to-End Data Flow

### A) Manual top-N read

1. API call: `GET /ingestion/accounts/1/messages/filtered/top-n?top_n=5`
2. Route calls `fetch_top_n_filtered_messages_for_one_account(1, 5)`.
3. Fetcher:
   - loads account + encrypted tokens
   - decrypts and builds credentials
   - calls Gmail list + message metadata APIs
4. Returns essential message fields only.

No schedule marker updates happen here (read-only fetch behavior).

---

### B) Manual incremental sync for one account

1. API call: `GET /ingestion/accounts/1/messages/filtered/latest`
2. Route calls `sync_latest_filtered_messages_for_one_account(1)`.
3. Poller:
   - runs incremental fetch
   - updates `last_history_id`
   - updates `last_polled_at`
4. Returns fetched message list and sync metadata.

---

### C) Automated loop sync

1. `run_poller_loop()` wakes up every ~30s.
2. Loads active accounts.
3. Filters accounts that are due by `polling_interval_min`.
4. Runs incremental sync for due accounts only.
5. Logs counts and sleeps again.

This keeps automation efficient while still allowing manual immediate sync calls.

---

## API Surface (Current)

Base prefix: `/ingestion`

- `GET /accounts/{account_id}/messages/raw/top-n?top_n=10`
  - Returns top N full/raw messages.

- `GET /accounts/{account_id}/messages/filtered/top-n?top_n=10`
  - Returns top N essential message fields.

- `GET /accounts/{account_id}/messages/filtered/latest`
  - Runs incremental sync for one account and returns fetched delta messages
    in filtered/essential format (no raw payload).

- `GET /accounts/messages/filtered/latest`
  - Runs immediate incremental sync for **all active accounts**.
  - Returns detailed per-account results with filtered messages
    (`From`, `Subject`, `Date`, snippet, normalized timestamps).

---

## Error and Edge Cases

- Account missing -> 404 or status `not_found`.
- Account inactive -> empty fetch or explicit inactive status (depending on route).
- No mailbox messages -> empty list (not an error).
- First incremental run with no `last_history_id`:
  - bootstrap-like behavior to establish history checkpoint.
  - may return zero messages but still set new `last_history_id`.

---

## Practical Examples

### Example 1: Bootstrap first

1. Connect Gmail account via auth flow.
2. Call:
   - `GET /ingestion/accounts/{id}/messages/raw/top-n?top_n=10`
3. Inspect recent message payloads.

### Example 2: Switch to incremental

1. Call:
   - `GET /ingestion/accounts/{id}/messages/filtered/latest`
2. Future calls pull only deltas since stored history id.

### Example 3: Immediate user-triggered sync

If user clicks “Sync now” in UI:
- call `GET /ingestion/accounts/{id}/messages/filtered/latest`
- sync runs immediately even if interval has not elapsed.

---

## Why This Architecture Scales

- Clear boundaries:
  - routes: HTTP
  - fetcher: Gmail API calls
  - poller: scheduling/state updates
- Supports both debugging and production automation.
- Makes future migration easier:
  - move from in-process loop to job queue/worker
  - add persistence for fetched raw messages
  - add retries/backoff per account

This structure is intentionally designed so ingestion can grow without tightly coupling
API handlers, scheduler logic, and Gmail client operations.
