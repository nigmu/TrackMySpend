"""Database schema, applied by migrate.py in order.

SMS pipeline: raw_sms_data, transactions_sms.
An SMS ledger row points at one raw_sms_data row via raw_sms_id.
A manual ledger row leaves raw_sms_id null. The ledger module writes the row.
POST /sms/ingest_and_parse and POST /sms/parse classify, then set
processing_status on the raw SMS.

app_event_logs is the activity feed for SMS and TMS Companion OTA.

The DROP statements remove the retired Gmail pipeline
(email_accounts, sender_filters, raw_mail_data, transactions, sync_runs)
and the OAuth tokens stored in email_accounts. Safe to run repeatedly.
"""

SCHEMA_STATEMENTS: list[str] = [
    "DROP TABLE IF EXISTS transactions CASCADE",
    "DROP TABLE IF EXISTS sync_runs CASCADE",
    "DROP TABLE IF EXISTS raw_mail_data CASCADE",
    "DROP TABLE IF EXISTS email_accounts CASCADE",
    "DROP TABLE IF EXISTS sender_filters CASCADE",
    """
    -- SMS pipeline (src/sms). Stored as received.
    -- content_hash (added below) dedupes on sender+body+device_id (not received_at).
    -- Parsed rows go to transactions_sms.
    CREATE TABLE IF NOT EXISTS raw_sms_data (
        id BIGSERIAL PRIMARY KEY,
        sender TEXT,
        body TEXT NOT NULL,
        received_at TIMESTAMPTZ,
        device_id TEXT,
        processing_status TEXT NOT NULL DEFAULT 'pending',
        error_message TEXT,
        content_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app_event_logs (
        id BIGSERIAL PRIMARY KEY,
        event_type TEXT NOT NULL,
        source TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'info',
        message TEXT NOT NULL,
        context JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_app_event_logs_created_at
        ON app_event_logs (created_at DESC, id DESC)
    """,
    """
    -- SMS ledger rows reference raw_sms_data. Manual ledger rows leave
    -- raw_sms_id null (many nulls are allowed under UNIQUE).
    -- sms_received_at is copied from raw_sms_data.received_at when apply
    -- writes the row. The SMS body is not parsed for a date. amount_paisa is
    -- null only for a bill reminder. A balance stores the available amount.
    -- Inserted by POST /sms/ingest_and_parse when a new row's classification
    -- has a ledger. POST /sms/parse updates that ledger row in place.
    CREATE TABLE IF NOT EXISTS transactions_sms (
        id BIGSERIAL PRIMARY KEY,
        raw_sms_id BIGINT UNIQUE
            REFERENCES raw_sms_data (id) ON DELETE CASCADE,
        kind TEXT NOT NULL CHECK (kind IN ('debit', 'credit', 'bill_reminder', 'balance')),
        amount_paisa BIGINT,
        instrument TEXT,
        account_mask TEXT,
        counterparty TEXT,
        reference TEXT,
        sms_received_at TIMESTAMPTZ,
        template_name TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT transactions_sms_amount_present CHECK (
            amount_paisa IS NOT NULL OR kind = 'bill_reminder'
        )
    )
    """,
    """
    ALTER TABLE transactions_sms DROP COLUMN IF EXISTS occurred_at
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'transactions_sms'
              AND column_name = 'received_at'
        ) THEN
            ALTER TABLE transactions_sms RENAME COLUMN received_at TO sms_received_at;
        ELSIF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'transactions_sms'
              AND column_name = 'sms_received_at'
        ) THEN
            ALTER TABLE transactions_sms ADD COLUMN sms_received_at TIMESTAMPTZ;
        END IF;
    END $$
    """,
    """
    ALTER TABLE transactions_sms
        ALTER COLUMN raw_sms_id DROP NOT NULL
    """,
    """
    ALTER TABLE transactions_sms
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
    """,
    """
    UPDATE transactions_sms
    SET updated_at = created_at
    WHERE updated_at IS NULL
    """,
    """
    ALTER TABLE transactions_sms
        ALTER COLUMN updated_at SET DEFAULT NOW()
    """,
    """
    ALTER TABLE transactions_sms
        ALTER COLUMN updated_at SET NOT NULL
    """,
    """
    ALTER TABLE transactions_sms DROP CONSTRAINT IF EXISTS transactions_sms_kind_check
    """,
    """
    ALTER TABLE transactions_sms
        ADD CONSTRAINT transactions_sms_kind_check
        CHECK (kind IN ('debit', 'credit', 'bill_reminder', 'balance'))
    """,
    """
    DELETE FROM app_event_logs
    WHERE source IN ('mail', 'gmail', 'accounts', 'filters')
       OR event_type LIKE 'gmail.%'
       OR event_type LIKE 'filter.%'
       OR event_type IN ('parse.completed', 'parse.failed')
    """,
]

# One-time compatibility: old test-server table `raw_sms` -> `raw_sms_data`.
# Split into two halves by migrate.py: statement [0] (the rename) must run
# BEFORE `CREATE TABLE IF NOT EXISTS raw_sms_data` above, otherwise the CREATE
# would win the race and silently strand any old `raw_sms` data. Statements
# [1:] (column adds, hash backfill, NOT NULL, unique index) must run AFTER,
# once the table is guaranteed to exist. Safe to delete this whole list once
# every deployment has migrated past the old `raw_sms` table name.
POST_SCHEMA_STATEMENTS: list[str] = [
    """
    DO $$
    BEGIN
        IF to_regclass('public.raw_sms') IS NOT NULL
           AND to_regclass('public.raw_sms_data') IS NULL THEN
            ALTER TABLE raw_sms RENAME TO raw_sms_data;
        END IF;
    END $$
    """,
    """
    ALTER TABLE raw_sms_data
        ADD COLUMN IF NOT EXISTS processing_status TEXT NOT NULL DEFAULT 'pending'
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_raw_sms_data_status_id
        ON raw_sms_data (processing_status, id)
    """,
    """
    ALTER TABLE raw_sms_data
        ADD COLUMN IF NOT EXISTS error_message TEXT
    """,
    """
    ALTER TABLE raw_sms_data
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    """,
    """
    ALTER TABLE raw_sms_data
        ADD COLUMN IF NOT EXISTS content_hash TEXT
    """,
    """
    UPDATE raw_sms_data
    SET content_hash = md5(
        COALESCE(sender, '') || E'\\n' ||
        body || E'\\n' ||
        COALESCE(device_id, '')
    )
    WHERE content_hash IS NULL
    """,
    """
    ALTER TABLE raw_sms_data
        ALTER COLUMN content_hash SET NOT NULL
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_sms_data_content_hash
        ON raw_sms_data (content_hash)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_raw_sms_data_received_at
        ON raw_sms_data (received_at DESC NULLS LAST)
    """,
]
