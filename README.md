# Project Structure

```text
src/
├── app.py                            # mounts auth, ingestion, pipeline routers
│
├── core/
│   ├── config.py                     # DATABASE_URL + DEFAULT_PARSER_FROM_HEADER_KEYWORDS
│   ├── logging/                      # untouched
│   └── security/
│       └── crypto.py                 # was src/security/crypto.py
│
├── db/
│   ├── connection.py                 # was src/db_connection.py
│   ├── dependencies.py               # was src/auth/dependencies.py
│   ├── schema.py                     # DDL list (now includes parser_sender_keywords)
│   └── migrate.py                    # python -m src.db.migrate
│
├── auth/                             # router + service + db (email_accounts only)
│   └── db.py                         # now also has update_last_polled_at,
│                                     # update_last_history_id,
│                                     # list_active_accounts,
│                                     # get_account_sync_state
│
├── ingestion/                        # NO db.py here
│   ├── routes.py
│   ├── service.py                    # was poller.py; calls pipeline/db.py + auth/db.py
│   └── gmail_client.py               # was email_fetcher.py
│
├── parsing/                          # PURE
│   ├── basic.py
│   ├── advanced_hdfc.py
│   └── tests/
│       ├── test_basic.py
│       └── test_advanced_hdfc.py
│
└── pipeline/
    ├── routes.py                     # /pipeline/keywords (G/P),
    │                                 # /stage1-to-stage2/run,
    │                                 # /transactions/load-from-staging
    │
    ├── db.py                         # SQL for stage1, stage2, transactions, keywords
    │
    ├── keywords.py                   # CRUD + DB-first/seed-fallback
    │
    ├── stage0_ingest_to_stage1.py    # gmail dicts -> stage 1
    │
    ├── stage1_to_stage2.py           # sender filter
    │
    └── stage2_to_transactions.py     # parse -> transactions (atomic)
```

