# TrackMySpend

TrackMySpend collects bank alerts from Gmail and Android SMS.

- **Gmail alerts** are filtered, stored, and parsed into transactions.
- **SMS alerts** are sent by TMS Companion and stored as raw messages. SMS-to-transaction parsing is not implemented yet.

Both pipelines use the same FastAPI service and PostgreSQL database. The web UI is a separate static site.

- Python: 3.12 or newer
- API: port `2006`
- Web UI: port `2007`
- Database: PostgreSQL

## How data flows

### Gmail

1. The user connects a Gmail account through OAuth.
2. TrackMySpend reads Gmail message metadata using the readonly Gmail scope.
3. Global sender filters keep only matching bank emails.
4. Matching messages are stored in `raw_mail_data`.
5. The parser extracts the first `Rs` or `INR` amount from the subject and snippet.
6. The amount is stored as integer paisa in `transactions`.

### SMS

1. TMS Companion receives an SMS on an Android phone.
2. The phone applies its own local sender filters.
3. Matching messages are sent to `POST /sms/ingest`.
4. The API stores them in `raw_sms_data`.
5. The web **SMS** page displays the stored messages.

Gmail filters and Android filters are separate. SMS messages are not added to `transactions`.

## Features

### Gmail accounts

- **Google OAuth:** `GET /auth/gmail/connect` starts a Gmail readonly OAuth flow. Google returns to `GET /auth/gmail/callback`.
- **Multiple accounts:** the Accounts page lists every connected Gmail account and its last polling time.
- **Encrypted tokens:** OAuth access and refresh tokens are encrypted with Fernet before they are stored in PostgreSQL.
- **Account removal:** connected accounts can be removed from the UI or with `DELETE /accounts/{account_id}`.

### Gmail synchronization

- **Initial sync:** the first sync searches for the latest 50 messages that match a configured sender filter.
- **Incremental sync:** later syncs use Gmail's History API to request only new messages.
- **Stale-history recovery:** if Gmail expires a saved history ID, TrackMySpend automatically performs another initial search.
- **Automatic polling:** the API checks for due accounts every minute. Each account is polled every 15 minutes by default.
- **Manual sync:** the UI can sync one account or all accounts through `POST /sync/{account_id}` and `POST /sync`.
- **Duplicate prevention:** Gmail message IDs are unique in `raw_mail_data`, so the same email is not stored twice.
- **Automatic parsing:** each manual or scheduled sync runs the pending-mail parser after ingestion.

### Gmail sender filters

- Filters are case-insensitive sender substrings. For example, `hdfcbank.bank.in` matches an address containing that text.
- Filters are shared by all connected Gmail accounts.
- The Filters page can list, add, and delete them through `GET /filters`, `POST /filters`, and `DELETE /filters/{filter_id}`.
- A Gmail sync is skipped when there are no active filters.

These filters apply only to Gmail. TMS Companion keeps its SMS filters on the phone.

### Mail and transactions

- **Raw Mail page:** shows received time, sender, subject, processing state, and the filter that matched.
- **Amount parsing:** the parser recognizes values beginning with `Rs`, `Rs.`, or `INR`, including commas and decimals.
- **Integer storage:** amounts are converted to paisa before database storage. For example, `Rs. 1,234.56` becomes `123456`.
- **Processing states:** raw mail is marked `pending`, `processing`, `done`, or `failed`.
- **Manual parse:** `POST /parse` retries the current batch of pending email rows.
- **Transactions page:** `GET /transactions` returns parsed Gmail amounts together with their source email details.

### SMS ingestion

- `POST /sms/ingest` accepts `message_id`, `sender`, `body`, `received_at`, and `device_id`.
- `body` is required. The other fields are optional at the API boundary.
- When `SMS_INGEST_TOKEN` is configured, the request must include the same value in `X-TrackMySpend-Token`.
- The API hashes the sender, body, and device ID (`content_hash`). A unique index prevents retries and live-vs-inbox reuploads from creating duplicate rows. `received_at` is stored but not part of the hash.
- `GET /sms` returns the stored raw SMS records ordered by `received_at` (newest first), not by insert `id`.

See [TMS Companion documentation](mobile_companion_app/README.md) for Android features, setup, delivery retries, and updates.

### Web UI

The frontend is plain HTML, CSS, and JavaScript. It has seven pages:

- **Home:** API status and totals for accounts, filters, mail, SMS, transactions, and events.
- **Accounts:** connect, list, sync, and remove Gmail accounts; sync all accounts or parse pending mail.
- **Filters:** add and delete Gmail sender filters.
- **Mail:** inspect raw matching Gmail alerts and processing states.
- **SMS:** inspect raw messages received from TMS Companion.
- **Transactions:** view amounts parsed from Gmail.
- **Logs:** view important application events.

The sidebar's **API base** field can temporarily point the UI at another API server. Its default comes from `API_PUBLIC_BASE` through generated file `frontend/js/env.js`.

### Logging and diagnostics

- Gmail connection, synchronization, parsing, SMS ingestion, and companion-manifest events are stored in `app_event_logs`.
- `GET /logs` returns these operational events for the web Logs page.
- HTTP requests, application messages, and exceptions are written to the console and rotating file `logs/app.log`.
- Every API response includes an `X-Request-ID`. A supplied `X-Request-ID` is preserved.
- Log level, location, JSON formatting, file size, and backup count are configurable.

### Companion updates

- `GET /app/update.json` serves `releases/companion/update.json`. `apk_url` in that file is a path; the response prefixes `API_PUBLIC_BASE`.
- `GET /releases/{filename}` serves APK files from `releases/companion/`.
- A missing or malformed manifest produces a safe fallback and an event-log entry.

## API routes

### Service

- `GET /` — API status and service message.
- `GET /health` — lightweight health check used by TMS Companion.
- `GET /docs` — interactive FastAPI documentation.

### Gmail accounts

- `GET /auth/gmail/connect` — start Gmail OAuth.
- `GET /auth/gmail/callback` — complete Gmail OAuth.
- `GET /accounts` — list connected accounts.
- `DELETE /accounts/{account_id}` — remove an account.

### Filters and mail

- `GET /filters` — list Gmail sender filters.
- `POST /filters` — add or reactivate a filter.
- `DELETE /filters/{filter_id}` — delete a filter.
- `POST /sync` — sync all active Gmail accounts, then parse pending mail.
- `POST /sync/{account_id}` — sync one account, then parse pending mail.
- `GET /mails` — list raw matching Gmail messages.
- `POST /parse` — parse pending raw mail.
- `GET /transactions` — list parsed Gmail transactions.

### SMS and logs

- `POST /sms/ingest` — receive an SMS from TMS Companion.
- `GET /sms` — list raw SMS messages.
- `GET /logs` — list application events.

### Android updates

- `GET /app/update.json` — return the Android update manifest. A path in `apk_url` is prefixed with `API_PUBLIC_BASE`.
- `GET /releases/{filename}` — download a published APK.

`GET /mails`, `GET /transactions`, `GET /sms`, and `GET /logs` accept `limit` and `offset`. The default limit is 50 and the maximum is 200.

## Project layout

```text
src/accounts/                     Gmail OAuth and connected accounts
src/filters/                      Gmail sender filters
src/mail/                         Gmail sync, polling, storage, and parsing
src/sms/                          SMS ingestion and deduplication
src/logs/                         Persistent application events
src/companion/                    Android update manifest route
src/core/                         Configuration, logging, encryption, and amount parsing
src/db/                           PostgreSQL schema and migrations
frontend/                         Static web UI
mobile_companion_app/android_app/ TMS Companion Android source
releases/companion/               Update manifest and published APKs
tests/                            Unit tests
```

## First-time setup

### 1. Create the Python environment

Run commands from the repository root.

**Linux and macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 2. Create `.env`

PostgreSQL must be installed and running.

**Linux and macOS**

```bash
cp .env.example .env
```

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

At minimum, set `DATABASE_URL`. Gmail also requires Google OAuth values and `ENCRYPTION_KEY`.

### 3. Install and migrate

With the virtual environment active:

```bash
pip install -e .
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -m src.db.migrate
```

Copy the generated key into `.env` as `ENCRYPTION_KEY`. Keep the same key after accounts are connected; changing it makes stored Gmail tokens unreadable.

### 4. Start the API

```bash
python main.py
```

Open `http://localhost:2006/health`. The expected response is:

```json
{"status":"ok"}
```

Starting the API also starts the Gmail poller and writes the frontend API configuration.

### 5. Start the web UI

In a second terminal:

```bash
python -m http.server 2007 --directory frontend
```

Open `http://localhost:2007`.

### 6. Connect Gmail

1. Configure a Google Cloud OAuth client with the Gmail readonly scope.
2. Register `{API_PUBLIC_BASE}/auth/gmail/callback` as an authorized redirect URI.
3. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `API_PUBLIC_BASE`, and `FRONTEND_ORIGIN` in `.env`.
4. Restart the API.
5. Open the matching frontend origin and select **Accounts → Connect Gmail**.
6. Add at least one Gmail sender filter.
7. Select **Sync all**.

Use a registered public hostname or localhost for OAuth. Google does not accept ordinary LAN IP addresses as web redirect URIs.

## Environment settings

- `DATABASE_URL` — PostgreSQL connection string.
- `GOOGLE_CLIENT_ID` — Google OAuth client ID.
- `GOOGLE_CLIENT_SECRET` — Google OAuth client secret.
- `ENCRYPTION_KEY` — Fernet key used to encrypt Gmail tokens.
- `API_PUBLIC_BASE` — public API origin, without a path or trailing slash.
- `FRONTEND_ORIGIN` — public web UI origin used for OAuth return and CORS.
- `CORS_EXTRA_ORIGINS` — comma-separated LAN or Tailscale UI origins.
- `PUBLIC_HOST` — fallback host only; derives `http://<host>:2006` and `http://<host>:2007` when explicit public origins are unset.
- `SMS_INGEST_TOKEN` — optional shared token required by `POST /sms/ingest`.
- `LOG_LEVEL` — Python log level; defaults to `INFO`.
- `LOG_DIR` — log directory; defaults to `logs`.
- `LOG_JSON` — use JSON log lines when set to `true`.
- `LOG_FILE_MAX_BYTES` — rotate `app.log` after this size; defaults to `2000000`.
- `LOG_FILE_BACKUP_COUNT` — number of rotated files to keep; defaults to `3`.

`API_PUBLIC_BASE`, `FRONTEND_ORIGIN`, and values in `CORS_EXTRA_ORIGINS` must use `http://` or `https://` and must not contain a path.

## Network access

Local addresses:

- API: `http://localhost:2006`
- UI: `http://localhost:2007`

`localhost` works only on the same machine. Other devices must use a LAN, Tailscale, or public address. Add every browser UI origin to `CORS_EXTRA_ORIGINS`.

The web UI uses one API base at a time. TMS Companion can keep up to three ordered API servers for retry and failover.

Only SMS ingestion has shared-token protection inside this application. If the API is exposed publicly, protect the remaining routes at the network or proxy layer. Any proxy access policy must still allow the companion to reach `/health`, `/sms/ingest`, `/app/update.json`, and `/releases/`.

## Database updates

Run the migration after pulling code that changes the schema:

```bash
python -m src.db.migrate
```

Then restart the API. Migrations are written to be safe to run repeatedly.

## Checks

With the virtual environment active:

```bash
python -m unittest discover -s tests -v
```

That discover loads the HDFC SMS parser checks in `src/sms/test_hdfc.py`.

Small module self-checks are also available:

```bash
python -m src.core.amount
python -m src.sms.db
```

## TMS Companion

TMS Companion runs on Android 8 or newer, filters bank SMS on the phone, and sends matching messages to this API.

See [mobile_companion_app/README.md](mobile_companion_app/README.md) for its complete feature list, build instructions, setup, delivery behavior, and update process.
