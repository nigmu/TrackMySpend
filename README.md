# TrackMySpend

Gmail bank alerts → `raw_mail_data` → amount-only `transactions`.

```
email_accounts + sender_filters
        │
     [sync]  ← poller every 15 min, or POST /sync
        │    only From matching a sender_filter
        ▼
  raw_mail_data
        │
     [parse] ← auto after sync, or POST /parse
        ▼
  transactions (amount_paisa)
```

## Setup

1. Postgres database + copy `.env.example` to `.env`.
2. Generate `ENCRYPTION_KEY`:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

3. Google Cloud OAuth client (Gmail readonly). Redirect URI must match `GOOGLE_REDIRECT_URI`.
4. Install and migrate:

   ```bash
   pip install -e .
   python -m src.db.migrate
   python main.py
   ```

   API: http://localhost:2006

5. Frontend:

   ```bash
   python -m http.server 2007 --directory frontend
   ```

   Open http://localhost:2007

## Ports

| Service | Port |
|---------|------|
| Main API | 2006 |
| Frontend UI | 2007 |
| SMS companion ingest | 2005 |

## Linux (systemd)

All three processes run together via `deploy/TrackMySpend.service` and `bin/trackmyspend-run.sh`. On the server:

```bash
chmod +x bin/trackmyspend-run.sh
sudo cp deploy/TrackMySpend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now TrackMySpend.service
```

Set `FRONTEND_ORIGIN` and `GOOGLE_REDIRECT_URI` in `.env` to match your host and these ports.

## APIs

- `GET /auth/gmail/connect` — start OAuth
- `GET /accounts` / `DELETE /accounts/{id}`
- `GET|POST /filters` / `DELETE /filters/{id}`
- `POST /sync` / `POST /sync/{account_id}`
- `POST /parse`
- `GET /mails` / `GET /transactions`

Parser self-check: `python -m src.parsing.amount`

## SMS companion (optional)

Phone SMS → Android companion → `POST /sms/ingest`. In-app OTA is manual (toolbar ☰). See [`mobile_companion_app/README.md`](mobile_companion_app/README.md).
