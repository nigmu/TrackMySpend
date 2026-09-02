# TrackMySpend

Personal tracker: Gmail bank alerts and phone SMS land in Postgres. Mail is parsed into amount-only `transactions`. SMS is stored raw for now.

```
email_accounts + sender_filters          Android companion (phone-local filters)
        │                                         │
     [sync]  poller ~15 min, or POST /sync        POST /sms/ingest
        │    From must match a sender_filter      optional X-TrackMySpend-Token
        ▼                                         ▼
  raw_mail_data                              raw_sms_data
        │
     [parse]  auto after sync, or POST /parse
        ▼
  transactions (amount_paisa)
```

Two processes, two ports:

| Process | Port | What it is |
|---------|------|------------|
| FastAPI (`python main.py` / uvicorn `src.app:app`) | 2006 | Gmail, SMS ingest, companion OTA, `/health` |
| Static UI (`python -m http.server --directory frontend`) | 2007 | Home, Accounts, Filters, Mail, SMS, Transactions, Logs |

There is no separate SMS server and no port 2005.

## Layout

```
src/                  FastAPI app
  accounts/           Gmail OAuth
  filters/            Gmail sender filters (server-side)
  ingestion/          Gmail sync → raw_mail_data
  parsing/            mail → transactions
  sms/                POST /sms/ingest, GET /sms
  companion/          GET /app/update.json
  logs/               GET /logs  (app_event_logs)
  core/               config, file logging, request logging
  db/                 schema + migrate
frontend/             static UI (port 2007)
releases/companion/   OTA manifest + APKs (served from port 2006)
mobile_companion_app/android_app/   Kotlin client
bin/trackmyspend-run.sh             API + UI together
deploy/TrackMySpend.service         systemd unit
```

## Setup

1. Postgres, then copy `.env.example` to `.env`.
2. Generate `ENCRYPTION_KEY`:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

3. Google Cloud OAuth client (Gmail readonly). Redirect URI must match `GOOGLE_REDIRECT_URI`.
4. Install, migrate, run API:

   ```bash
   pip install -e .
   python -m src.db.migrate
   python main.py
   ```

   API: http://localhost:2006  
   Health: http://localhost:2006/health → `{"status":"ok"}`

5. Frontend:

   ```bash
   python -m http.server 2007 --directory frontend
   ```

   Open http://localhost:2007  
   Sidebar **API base** defaults to `http://localhost:2006`. On another machine, set it to `http://<api-host>:2006`.

After pulling schema changes on a deployed box, run `python -m src.db.migrate` again, then restart the service.

## Environment

Copy `.env.example`. Used values:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql://postgres:postgres@127.0.0.1:5432/trackmyspend` | Postgres |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | empty | Gmail OAuth |
| `GOOGLE_REDIRECT_URI` | `http://localhost:2006/auth/gmail/callback` | Must match the Google client |
| `ENCRYPTION_KEY` | empty | Fernet key for OAuth tokens |
| `FRONTEND_ORIGIN` | `http://localhost:2007` | CORS + OAuth return URL |
| `SMS_INGEST_TOKEN` | empty | If set, `POST /sms/ingest` requires header `X-TrackMySpend-Token` |
| `LOG_LEVEL` | `INFO` | File + console logs |
| `LOG_DIR` | `logs` | Directory for `app.log` |
| `LOG_JSON` | `false` | `true` writes JSON lines instead of text |
| `LOG_FILE_MAX_BYTES` | `2000000` | Rotate size |
| `LOG_FILE_BACKUP_COUNT` | `3` | Rotated files to keep |

## Logging

- **File / console:** request line (method, path, status, duration, client, request id) plus domain logs → `logs/app.log` (gitignored).
- **UI Logs page:** product events in `app_event_logs` (Gmail connect/sync, parse, SMS ingest, companion manifest). Not every HTTP request.

## APIs (port 2006)

- `GET /` — UI health probe
- `GET /health` — Android **Test** button (`{"status":"ok"}`)
- `GET /auth/gmail/connect` — start OAuth
- `GET /accounts` / `DELETE /accounts/{id}`
- `GET|POST /filters` / `DELETE /filters/{id}` — Gmail sender filters
- `POST /sync` / `POST /sync/{account_id}`
- `POST /parse`
- `GET /mails` / `GET /transactions`
- `POST /sms/ingest` — `{sender?, body, received_at?, device_id?}`; duplicates skipped via `content_hash`
- `GET /sms`
- `GET /logs`
- `GET /app/update.json`
- `GET /releases/{filename}` — files from `releases/companion/`

Self-checks:

```bash
python -m src.parsing.amount
python -m src.sms.db
```

## Linux (systemd)

API **2006** and UI **2007** start together via `deploy/TrackMySpend.service` and `bin/trackmyspend-run.sh`:

```bash
chmod +x bin/trackmyspend-run.sh
sudo cp deploy/TrackMySpend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now TrackMySpend.service
```

Set `FRONTEND_ORIGIN` and `GOOGLE_REDIRECT_URI` in `.env` to the host and these ports. After code or schema updates on the box:

```bash
python -m src.db.migrate
sudo systemctl restart TrackMySpend
```

## SMS companion

Phone SMS → Android app → `POST /sms/ingest` on **2006**. Phone sender filters are local to the app; they are not the Gmail `sender_filters` on the server. OTA is manual (toolbar ☰).

See [`mobile_companion_app/README.md`](mobile_companion_app/README.md).
