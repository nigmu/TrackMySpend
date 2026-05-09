To visualize the SCHEMA: https://dbdiagram.io/d/TrackMySpend-69dab2658089629684744c1b

# Database schema reference

This document describes **indexes**, **PL/pgSQL functions**, and **triggers** defined in `src/db/schema.py` (applied via `python -m src.db.migrate`). Canonical table layout is also in `DB/schema.dbml`.

PostgreSQL **14+** is assumed: triggers use `EXECUTE FUNCTION` (see `CREATE TRIGGER` in current PostgreSQL docs).

---

## Indexes

### Declared explicitly in `schema.py`

| Index name | Table | Columns | Purpose |
|------------|--------|---------|---------|
| `idx_email_raw_ingest_etl_status_id` | `email_raw_ingest` | `(etl_status, id)` | Speeds scans that filter by pipeline state (e.g. `etl_status = 'PENDING'`) and order by `id`, matching the stage-1 sender-filter query pattern. |
| `idx_email_parse_queue_etl_status_id` | `email_parse_queue` | `(etl_status, id)` | Same pattern for the stage-2 parse queue (e.g. pending rows ordered by `id`). |

### Created implicitly by constraints

PostgreSQL builds a ** btree index** for each `PRIMARY KEY` and each `UNIQUE` constraint. You do not see a separate `CREATE INDEX` for these in `schema.py`, but they exist after migration:

| Table | Constraint type | Column(s) | Effect |
|--------|-----------------|-----------|--------|
| `user_email_accounts` | PRIMARY KEY | `id` | Unique row id; index supports joins and lookups by id. |
| `user_email_accounts` | UNIQUE | `email_address` | One row per address; fast lookup by email. |
| `email_raw_ingest` | PRIMARY KEY | `id` | Unique raw row id. |
| `email_raw_ingest` | UNIQUE | `gmail_message_id` | Global uniqueness on Gmail message id; supports `ON CONFLICT (gmail_message_id)` in the app. |
| `email_parse_queue` | PRIMARY KEY | `id` | Unique queue row id. |
| `email_parse_queue` | UNIQUE | `raw_ingest_id` | At most one parse-queue row per raw ingest row. |
| `transactions` | PRIMARY KEY | `id` | Unique transaction id. |
| `filter_keywords` | PRIMARY KEY | `id` | Unique keyword row id. |
| `filter_keywords` | UNIQUE | `keyword` | One row per filter string; supports `ON CONFLICT (keyword)`. |

**Note:** Foreign keys (`REFERENCES …`) do **not** automatically create an index on the referencing column in PostgreSQL. The app does not add a standalone index on e.g. `transactions.parse_queue_id` or `email_raw_ingest.email_account_id` today; add one if monitoring shows slow joins or deletes.

---

## Functions (trigger functions)

All three are **trigger functions**: they return `TRIGGER` and are only meant to be invoked from triggers, not called directly from application SQL.

### `trg_user_email_accounts_etl_update()`

- **Role:** On **every** `UPDATE` to `user_email_accounts`, sets `NEW.etl_update_ts` to `NOW()` before the row is written.
- **Why:** `etl_update_ts` always reflects the last modification time, regardless of which columns changed (tokens, polling interval, `last_polled_at`, `last_history_id`, etc.).

### `trg_email_raw_ingest_etl_status_update()`

- **Role:** On `UPDATE` of `email_raw_ingest`, if `etl_status` actually changed (`IS DISTINCT FROM`), sets `NEW.etl_update_ts` to `NOW()`.
- **Why:** `etl_update_ts` tracks **lifecycle** changes (e.g. `PENDING` → `DONE` / `SKIPPED`), not every touch of snippet or payload fields if you later widen updates.

### `trg_email_parse_queue_etl_status_update()`

- **Role:** Same conditional rule as the raw-ingest function, but for `email_parse_queue` when `etl_status` changes (e.g. `PENDING` → `PARSED`).
- **Why:** Aligns queue “state transition” semantics with `etl_update_ts` on the parse queue table.

---

## Triggers

Each trigger is recreated idempotently: `DROP TRIGGER IF EXISTS …` then `CREATE TRIGGER …`.

| Trigger name | Table | Timing | Event | Calls |
|--------------|--------|--------|-------|--------|
| `trg_user_email_accounts_bu` | `user_email_accounts` | `BEFORE` | `UPDATE` (each row) | `trg_user_email_accounts_etl_update()` |
| `trg_email_raw_ingest_bu` | `email_raw_ingest` | `BEFORE` | `UPDATE` (each row) | `trg_email_raw_ingest_etl_status_update()` |
| `trg_email_parse_queue_bu` | `email_parse_queue` | `BEFORE` | `UPDATE` (each row) | `trg_email_parse_queue_etl_status_update()` |

The suffix `_bu` indicates **before update**.

`transactions` and `filter_keywords` have **no** triggers in this schema: `transactions` is insert-heavy from the app today, and `filter_keywords` only needs `etl_insert_ts` on insert (default `NOW()`).

---

## Related application behavior

- **Raw ingest / parse queue `etl_status` values** used in Python include `PENDING`, `DONE`, `SKIPPED`, and `PARSED` (see `src/pipeline/db.py` and stage modules).
- **Migrate entrypoint:** `src/db/migrate.py` runs each statement in `SCHEMA_STATEMENTS` in order.
