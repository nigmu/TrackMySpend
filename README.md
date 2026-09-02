# TrackMySpend

TrackMySpend saves bank alerts from two places:

1. **Gmail** — bank emails are synced, then parsed into amounts (rupees stored as paisa).
2. **SMS** — the Android app sends matching texts to the server. They are stored as-is. They are **not** turned into amounts yet.

Both use the same Postgres database and the same API.

## Ports

You run two things:

| What | Port | How to start |
|------|------|----------------|
| API (Gmail, SMS ingest, app updates, health check) | 2006 | `python main.py` |
| Web UI | 2007 | `python -m http.server 2007 --directory frontend` |

Open the UI at http://localhost:2007  
The API is at http://localhost:2006

There is no extra SMS server. Do not use port 2005.

## How data flows

**Gmail**

1. Connect a Gmail account in the UI.
2. Add a sender filter (for example `hdfcbank.bank.in`). Only matching emails are kept.
3. Sync runs every ~15 minutes, or when you click **Sync all**.
4. Matching emails go into `raw_mail_data`.
5. Parse turns those emails into `transactions` (amount only).

**SMS**

1. Install the Android companion app on a real phone.
2. Add a sender filter on the phone (for example `HDFCBK`). These filters live on the phone, not in the web UI.
3. Add the API URL, for example `http://192.168.1.63:2006`.
4. Matching SMS are posted to `/sms/ingest` and stored in `raw_sms_data`.
5. You can see them on the web **SMS** page. They are not parsed into transactions yet.

## Folder layout

```
src/mail/                         Gmail sync, parse, poller
src/sms/                          SMS ingest
src/accounts/                     Gmail login (OAuth)
src/filters/                      Gmail sender filters (web UI)
src/companion/                    Android app update files
src/logs/                         Event log shown on the Logs page
src/core/                         Config, logging, encryption, amount helper
src/db/                           Database schema and migrate
frontend/                         Web UI
releases/companion/               Android APK + update.json
mobile_companion_app/android_app/ Android app source
bin/trackmyspend-run.sh           Starts API + UI together (Linux)
deploy/TrackMySpend.service       systemd unit (Linux)
```

## Setup (first time)

### 1. Database and env file

Postgres must be running. Then:

```bash
copy .env.example .env
```

On Linux/macOS: `cp .env.example .env`

### 2. Encryption key

Paste the printed value into `.env` as `ENCRYPTION_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Gmail (only if you want email alerts)

Create a Google Cloud OAuth client with Gmail **readonly**.

Set in `.env`:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI` — must match Google Console exactly, usually  
  `http://localhost:2006/auth/gmail/callback`

### 4. Install Python package and create tables

```bash
pip install -e .
python -m src.db.migrate
```

### 5. Start the API

```bash
python main.py
```

Check it is up: open http://localhost:2006/health  
You should see `{"status":"ok"}`.

### 6. Start the web UI (second terminal)

```bash
python -m http.server 2007 --directory frontend
```

Open http://localhost:2007

If the UI is on another machine, change **API base** in the sidebar to `http://<api-host>:2006`.

After you pull code that changes the database, run `python -m src.db.migrate` again, then restart the API.

## `.env` settings

| Name | What it does |
|------|----------------|
| `DATABASE_URL` | Postgres connection string |
| `GOOGLE_CLIENT_ID` | Gmail OAuth |
| `GOOGLE_CLIENT_SECRET` | Gmail OAuth |
| `GOOGLE_REDIRECT_URI` | Must match the Google Cloud client |
| `ENCRYPTION_KEY` | Encrypts Gmail tokens in the database |
| `FRONTEND_ORIGIN` | Web UI origin (CORS + after Google login) |
| `SMS_INGEST_TOKEN` | Optional. If set, the phone must send the same value as header `X-TrackMySpend-Token` |
| `LOG_LEVEL` | Log verbosity (`INFO` is fine) |
| `LOG_DIR` | Folder for `app.log` |
| `LOG_JSON` | `true` = JSON log lines |
| `LOG_FILE_MAX_BYTES` | Rotate log file after this size |
| `LOG_FILE_BACKUP_COUNT` | How many old log files to keep |

## Web UI pages

| Page | What you see |
|------|----------------|
| Home | Whether the API is up, plus counts |
| Accounts | Connected Gmail accounts; Sync / Parse |
| Filters | Gmail sender patterns (emails only) |
| Mail | Raw bank emails |
| SMS | Raw SMS from the phone |
| Transactions | Amounts parsed from **Gmail only** |
| Logs | Important events (sync, SMS ingest, etc.) |

Server logs also go to `logs/app.log`.

## API (port 2006)

Useful endpoints:

- `GET /health` — phone **Test** button uses this
- `GET /auth/gmail/connect` — start Gmail login
- `GET /accounts` — list accounts
- `DELETE /accounts/{id}` — remove an account
- `GET /filters` / `POST /filters` / `DELETE /filters/{id}` — Gmail filters
- `POST /sync` — sync all Gmail accounts
- `POST /sync/{account_id}` — sync one account
- `POST /parse` — parse pending emails into transactions
- `GET /mails` — raw emails
- `GET /transactions` — parsed amounts (from email)
- `POST /sms/ingest` — body: `sender`, `body` (required), `received_at`, `device_id`
- `GET /sms` — raw SMS
- `GET /logs` — event log
- `GET /app/update.json` — Android update info
- `GET /releases/{filename}` — APK files from `releases/companion/`

## Checks

Quick sanity checks (no database needed for the amount one):

```bash
python -m src.core.amount
python -m src.sms.db
python -m unittest discover -s tests -v
```

## Linux (always-on with systemd)

This starts both the API (2006) and the UI (2007):

```bash
chmod +x bin/trackmyspend-run.sh
sudo cp deploy/TrackMySpend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now TrackMySpend.service
```

In `.env` on that machine, set `FRONTEND_ORIGIN` and `GOOGLE_REDIRECT_URI` to the real host and ports.

After code or database changes:

```bash
python -m src.db.migrate
sudo systemctl restart TrackMySpend
```

## Android companion

The phone app sends SMS to this API on port **2006**.

Setup: [mobile_companion_app/README.md](mobile_companion_app/README.md)  
Build/install: [mobile_companion_app/android_app/README.md](mobile_companion_app/android_app/README.md)
