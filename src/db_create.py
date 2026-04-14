import sqlite3
from pathlib import Path

DB_PATH = Path("DB/data/trackmyspend.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;


CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL UNIQUE,
  value TEXT NOT NULL,
  description TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS email_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  email_address TEXT NOT NULL UNIQUE,
  oauth_access_token TEXT NOT NULL,
  oauth_refresh_token TEXT NOT NULL,
  polling_interval_min INTEGER DEFAULT 60,
  last_polled_at TEXT,
  is_active INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sms_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  phone_number TEXT NOT NULL UNIQUE,
  carrier TEXT,
  is_active INTEGER DEFAULT 1,
  last_parsed_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS parse_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email_account_id INTEGER,
  sms_source_id INTEGER,
  source_type TEXT NOT NULL,
  status TEXT NOT NULL,
  input_preview TEXT,
  llm_input TEXT,
  llm_output TEXT,
  transactions_extracted INTEGER DEFAULT 0,
  error_message TEXT,
  started_at TEXT,
  completed_at TEXT,
  FOREIGN KEY (email_account_id) REFERENCES email_accounts(id),
  FOREIGN KEY (sms_source_id) REFERENCES sms_sources(id)
);

CREATE TABLE IF NOT EXISTS bank_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  display_name TEXT NOT NULL,
  account_type TEXT NOT NULL,
  bank_name TEXT,
  account_number_masked TEXT,
  credit_limit REAL,
  billing_cycle_day INTEGER,
  due_day INTEGER,
  current_balance REAL,
  balance_updated_at TEXT,
  is_active INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS balance_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bank_account_id INTEGER NOT NULL,
  balance REAL NOT NULL,
  snapshot_date TEXT NOT NULL,
  source TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_balance_snapshots_account_date
ON balance_snapshots (bank_account_id, snapshot_date);

CREATE TABLE IF NOT EXISTS credit_card_statements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bank_account_id INTEGER NOT NULL,
  statement_date TEXT NOT NULL,
  due_date TEXT NOT NULL,
  total_due REAL NOT NULL,
  min_due REAL,
  paid_amount REAL DEFAULT 0,
  paid_at TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id)
);

CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  parent_id INTEGER,
  color TEXT,
  icon TEXT,
  is_system INTEGER DEFAULT 0,
  is_active INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (parent_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS merchants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  display_name TEXT NOT NULL,
  canonical_name TEXT,
  identifiers TEXT,
  default_category_id INTEGER,
  alias TEXT,
  notes TEXT,
  is_verified INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT,
  FOREIGN KEY (default_category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS income_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  expected_amount REAL,
  bank_account_id INTEGER,
  expected_day_type TEXT,
  expected_date INTEGER,
  is_active INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id)
);

CREATE TABLE IF NOT EXISTS salary_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  income_source_id INTEGER NOT NULL UNIQUE,
  working_days TEXT,
  last_day_override TEXT,
  updated_at TEXT,
  FOREIGN KEY (income_source_id) REFERENCES income_sources(id)
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  bank_account_id INTEGER NOT NULL,
  merchant_id INTEGER,
  category_id INTEGER,
  income_source_id INTEGER,
  parse_job_id INTEGER,
  amount REAL NOT NULL,
  direction TEXT NOT NULL,
  txn_type TEXT,
  description TEXT,
  notes TEXT,
  txn_date TEXT NOT NULL,
  value_date TEXT,
  reference_number TEXT,
  balance_after REAL,
  source TEXT NOT NULL,
  is_transfer INTEGER DEFAULT 0,
  is_deleted INTEGER DEFAULT 0,
  deleted_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id),
  FOREIGN KEY (merchant_id) REFERENCES merchants(id),
  FOREIGN KEY (category_id) REFERENCES categories(id),
  FOREIGN KEY (parse_job_id) REFERENCES parse_jobs(id),
  FOREIGN KEY (income_source_id) REFERENCES income_sources(id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_account_date
ON transactions (bank_account_id, txn_date);

CREATE INDEX IF NOT EXISTS idx_transactions_merchant
ON transactions (merchant_id);

CREATE INDEX IF NOT EXISTS idx_transactions_category
ON transactions (category_id);

CREATE INDEX IF NOT EXISTS idx_transactions_direction_date
ON transactions (direction, txn_date);

CREATE TABLE IF NOT EXISTS transaction_tags (
  transaction_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  PRIMARY KEY (transaction_id, tag_id),
  FOREIGN KEY (transaction_id) REFERENCES transactions(id),
  FOREIGN KEY (tag_id) REFERENCES tags(id)
);

CREATE TABLE IF NOT EXISTS transaction_attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  transaction_id INTEGER NOT NULL,
  file_path TEXT NOT NULL,
  file_type TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);

CREATE TABLE IF NOT EXISTS splits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  parent_txn_id INTEGER NOT NULL,
  total_amount REAL NOT NULL,
  user_share REAL NOT NULL,
  notes TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT,
  FOREIGN KEY (parent_txn_id) REFERENCES transactions(id)
);

CREATE TABLE IF NOT EXISTS split_participants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  split_id INTEGER NOT NULL,
  person_name TEXT NOT NULL,
  merchant_id INTEGER,
  owed_amount REAL NOT NULL,
  paid_amount REAL DEFAULT 0,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT,
  FOREIGN KEY (split_id) REFERENCES splits(id),
  FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);

CREATE TABLE IF NOT EXISTS split_settlements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  split_participant_id INTEGER NOT NULL,
  transaction_id INTEGER NOT NULL,
  amount REAL NOT NULL,
  settled_at TEXT NOT NULL,
  notes TEXT,
  FOREIGN KEY (split_participant_id) REFERENCES split_participants(id),
  FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);

CREATE TABLE IF NOT EXISTS split_reminders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  split_participant_id INTEGER NOT NULL,
  reminded_at TEXT NOT NULL,
  channel TEXT,
  message_preview TEXT,
  FOREIGN KEY (split_participant_id) REFERENCES split_participants(id)
);

CREATE TABLE IF NOT EXISTS holidays (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS budgets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER NOT NULL,
  period_type TEXT NOT NULL,
  amount REAL NOT NULL,
  alert_threshold_pct INTEGER DEFAULT 80,
  is_active INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT,
  FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS recurring_transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  merchant_id INTEGER,
  category_id INTEGER,
  label TEXT,
  expected_amount REAL,
  amount_tolerance_pct INTEGER DEFAULT 5,
  frequency TEXT NOT NULL,
  expected_day INTEGER,
  last_seen_at TEXT,
  next_expected_at TEXT,
  auto_detected INTEGER DEFAULT 1,
  is_active INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (merchant_id) REFERENCES merchants(id),
  FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS planned_expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  amount REAL NOT NULL,
  expected_date TEXT,
  category_id INTEGER,
  notes TEXT,
  is_fulfilled INTEGER DEFAULT 0,
  linked_txn_id INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY (category_id) REFERENCES categories(id),
  FOREIGN KEY (linked_txn_id) REFERENCES transactions(id)
);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  entity_type TEXT,
  entity_id INTEGER,
  is_read INTEGER DEFAULT 0,
  is_dismissed INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  read_at TEXT,
  dismissed_at TEXT
);

CREATE TABLE IF NOT EXISTS system_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  level TEXT NOT NULL,
  action_type TEXT NOT NULL,
  entity_type TEXT,
  entity_id INTEGER,
  old_value TEXT,
  new_value TEXT,
  ip_address TEXT,
  user_agent TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_system_logs_action_created
ON system_logs (action_type, created_at);

CREATE INDEX IF NOT EXISTS idx_system_logs_entity
ON system_logs (entity_type, entity_id);

"""

SEED_SQL = """
INSERT OR IGNORE INTO app_settings (key, value, description, updated_at) VALUES
  ('default_currency',             'INR',   'Currency used across the app',              NULL),
  ('log_retention_days',           '365',   'How long system logs are kept',             NULL),
  ('llm_model',                    'gpt-4o','LLM model used for parsing and annotation', NULL),
  ('anomaly_threshold_multiplier', '3',     'Flag txn if Nx above merchant average',     NULL),
  ('salary_alert_grace_days',      '1',     'Days after salary day before alert fires',  NULL),
  ('budget_alert_threshold_pct',   '80',    'Alert when this % of budget is consumed',   NULL);

INSERT OR IGNORE INTO categories (name, parent_id, color, is_system, is_active, created_at) VALUES
  ('Food',          NULL, '#E85D04', 1, 1, datetime('now')),
  ('Transport',     NULL, '#3A86FF', 1, 1, datetime('now')),
  ('Health',        NULL, '#2DC653', 1, 1, datetime('now')),
  ('Utilities',     NULL, '#FFBE0B', 1, 1, datetime('now')),
  ('Entertainment', NULL, '#8338EC', 1, 1, datetime('now')),
  ('Shopping',      NULL, '#FB5607', 1, 1, datetime('now')),
  ('Investment',    NULL, '#06D6A0', 1, 1, datetime('now')),
  ('EMI / Loan',    NULL, '#EF233C', 1, 1, datetime('now')),
  ('Salary',        NULL, '#4CC9F0', 1, 1, datetime('now')),
  ('Transfers',     NULL, '#B5B5B5', 1, 1, datetime('now')),
  ('Miscellaneous', NULL, '#6C757D', 1, 1, datetime('now'));
"""

def seed_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SEED_SQL)
    conn.commit()

def create_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        seed_db(conn)
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    create_db()
    print(f"Database created at: {DB_PATH}")