To visualize the SCHEMA: https://dbdiagram.io/d/TrackMySpend-69dab2658089629684744c1b

## Applying schema changes

- **Source of truth:** `DB/schema.dbml` (diagram) and `src/db_create.py` (executable SQLite DDL used at runtime).
- **New database:** with the app stopped, remove `DB/data/trackmyspend.db` if present, then run `python src/db_create.py` from the repo root.
- **Existing database:** stop anything holding the DB open, then run `python src/migrate_sqlite.py` (or `--dry-run` first). This rebuilds `email_parse_queue_staging` when `stg1_id` is missing and drops legacy `transactions.gmail_message_id` when present.