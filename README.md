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

On this machine the UI is http://localhost:2007 and the API is http://localhost:2006.

Three ways to reach the same server (no automatic failover — pick one):

| Path | API | UI |
|------|-----|-----|
| Cloudflare (primary) | https://server-trackmyspend.nigmulabs.xyz | https://trackmyspend.nigmulabs.xyz |
| Tailscale | Tailscale address, port 2006 | Tailscale address, port 2007 |
| LAN (other devices) | LAN address, port 2006 | LAN address, port 2007 |

`localhost` only works on the server. Phones and other PCs on Wi‑Fi use the machine’s LAN address. Put those UI origins in `CORS_EXTRA_ORIGINS`.

Commands below are **Linux first**. **macOS** uses the same commands unless a note says otherwise. **Windows** uses PowerShell where the command is different.

There is no extra SMS server. Do not use port 2005.

## How data flows

**Gmail**

1. Connect a Gmail account in the UI.
2. Add a sender filter (for example `hdfcbank.bank.in`). Only matching emails are kept.
3. Sync runs every ~15 minutes, or when you click **Sync all**.
4. Matching emails go into `raw_mail_data`.
5. Parse turns those emails into `transactions` (amount only).

**SMS**

1. Install TMS Companion on a real phone.
2. Add a sender filter on the phone (for example `HDFCBK`). These filters live on the phone, not in the web UI.
3. Add the API URL. Primary: `https://server-trackmyspend.nigmulabs.xyz`. Optionally add Tailscale and LAN backups (`http://<host>:2006`). Set **Active** on the tunnel URL.
4. Matching SMS are posted to `/sms/ingest` and stored in `raw_sms_data`.
5. You can see them on the web **SMS** page. They are not parsed into transactions yet.

## Folder layout

```
src/mail/                         Gmail sync, parse, poller
src/sms/                          SMS ingest
src/accounts/                     Gmail login (OAuth)
src/filters/                      Gmail sender filters (web UI)
src/companion/                    TMS Companion OTA update files
src/logs/                         Event log shown on the Logs page
src/core/                         Config, logging, encryption, amount helper
src/db/                           Database schema and migrate
frontend/                         Web UI
releases/companion/               TMS Companion APK + update.json
mobile_companion_app/android_app/ TMS Companion source
bin/trackmyspend-run.sh           Starts API + UI together (Linux)
deploy/TrackMySpend.service       systemd unit (Linux)
```

## Setup (first time)

Stay in the project folder for every command. After step 1, keep the venv **activated** in each terminal you use (**Linux** / **macOS** / **Windows**).

### 1. Create a virtual environment and turn it on

**Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**macOS** — same as Linux.

**Windows** (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try activate again.

Your prompt should show `(.venv)`. The Linux systemd unit expects this folder to be named `.venv`.

On Linux and macOS, after activate, use `python` and `pip` (not `python3`). On Windows, use `python` and `pip` from the venv as well.

### 2. Database and env file

Postgres must be running. Then copy the example env file.

**Linux** and **macOS**

```bash
cp .env.example .env
```

**Windows** (PowerShell)

```powershell
copy .env.example .env
```

Edit `.env` and set `DATABASE_URL` to your Postgres user, password, and database name.

### 3. Gmail OAuth (only if you want email alerts)

Create a Google Cloud OAuth client with Gmail **readonly**.

Set in `.env`:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `API_PUBLIC_BASE` — public API URL (Cloudflare). Google Console redirect must be  
  `{API_PUBLIC_BASE}/auth/gmail/callback`  
  (this machine: `https://server-trackmyspend.nigmulabs.xyz/auth/gmail/callback`)
- `FRONTEND_ORIGIN` — public UI URL (OAuth return). This machine: `https://trackmyspend.nigmulabs.xyz`
- `SMS_INGEST_TOKEN` — required once the API is on the internet; the phone must send the same value as header `X-TrackMySpend-Token`

Connect Gmail from the public UI (`https://trackmyspend.nigmulabs.xyz`), not from a LAN IP. Google rejects private-IP redirect URIs.

If you are not using a public hostname, omit `API_PUBLIC_BASE` / `FRONTEND_ORIGIN` and set `PUBLIC_HOST` (host only, no scheme/port) to derive `http://<host>:2006` and `:2007`.

### 4. Install Python packages, encryption key, and tables

**Linux**, **macOS**, and **Windows** (venv must be on):

```bash
pip install -e .
```

Print a key and paste it into `.env` as `ENCRYPTION_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then create the tables:

```bash
python -m src.db.migrate
```

### 5. Start the API

**Linux**, **macOS**, and **Windows** (venv on):

```bash
python main.py
```

Check it is up: open http://localhost:2006/health  
You should see `{"status":"ok"}`.

### 6. Start the web UI (second terminal)

Activate the venv in this terminal too (Linux/macOS: `source .venv/bin/activate` — Windows: `.\.venv\Scripts\Activate.ps1`), then:

**Linux**, **macOS**, and **Windows**

```bash
python -m http.server 2007 --directory frontend
```

Open http://localhost:2007 (or https://trackmyspend.nigmulabs.xyz).

API base in the UI comes from `API_PUBLIC_BASE` in `.env` (written to `frontend/js/env.js` when the API starts).

### 7. Log in with Gmail

1. Open the public UI (`https://trackmyspend.nigmulabs.xyz`), then **Accounts**.
2. Click **Connect Gmail**.
3. Sign in with the Google account that receives bank emails, and allow access.
4. You should return to the UI with that account listed.
5. On **Filters**, add a bank sender pattern (for example `hdfcbank.bank.in`).
6. Click **Sync all**, then **Parse pending**, to pull mail and fill **Transactions**.

Without this login, Gmail sync will not run. SMS from the phone does not use Google login.

After you pull code that changes the database, activate `.venv`, run `python -m src.db.migrate` again, then restart the API.

## `.env` settings

| Name | What it does |
|------|----------------|
| `DATABASE_URL` | Postgres connection string |
| `GOOGLE_CLIENT_ID` | Gmail OAuth |
| `GOOGLE_CLIENT_SECRET` | Gmail OAuth |
| `API_PUBLIC_BASE` | Public API URL (OAuth redirect + UI default). Example: `https://server-trackmyspend.nigmulabs.xyz` |
| `FRONTEND_ORIGIN` | Public UI origin (OAuth return + CORS). Example: `https://trackmyspend.nigmulabs.xyz` |
| `CORS_EXTRA_ORIGINS` | Extra UI origins (LAN / Tailscale), comma-separated |
| `PUBLIC_HOST` | Fallback host only (no scheme/port) if the two bases above are unset |
| `ENCRYPTION_KEY` | Encrypts Gmail tokens in the database |
| `SMS_INGEST_TOKEN` | Required when the API is public. Phone sends it as `X-TrackMySpend-Token` |
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

Quick sanity checks (venv on; no database needed for the amount one). Same on **Linux**, **macOS**, and **Windows**:

```bash
python -m src.core.amount
python -m src.sms.db
python -m unittest discover -s tests -v
```

## Always-on server (Linux systemd)

This is **Linux only** (systemd). It starts both the API (2006) and the UI (2007). Create `.venv` and install the app first (setup steps above).

```bash
chmod +x bin/trackmyspend-run.sh
sudo cp deploy/TrackMySpend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now TrackMySpend.service
```

In `.env` on that machine, set `API_PUBLIC_BASE` and `FRONTEND_ORIGIN` to the Cloudflare URLs (see table at the top). Match Google Console redirect to `{API_PUBLIC_BASE}/auth/gmail/callback`. Put LAN and Tailscale UI origins in `CORS_EXTRA_ORIGINS`. If Cloudflare Access is used, put it on the **UI** host only — Access on the whole API would block TMS Companion SMS ingest unless `/sms/ingest` is bypassed.

After code or database changes:

```bash
source .venv/bin/activate
python -m src.db.migrate
sudo systemctl restart TrackMySpend
```

On **macOS** or **Windows**, there is no systemd unit here — keep `python main.py` and the UI server running yourself (two terminals), or use another process manager.

## TMS Companion

The phone app sends SMS to this API. Add the tunnel as the first Servers entry: `https://server-trackmyspend.nigmulabs.xyz`. Optionally add Tailscale and LAN backups (`http://<host>:2006`).

Setup, features, build, and updates: [mobile_companion_app/README.md](mobile_companion_app/README.md)
