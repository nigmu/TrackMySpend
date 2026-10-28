# TrackMySpend

TrackMySpend collects bank alerts from Gmail and Android SMS.

- **Gmail alerts** are filtered, stored, and parsed into transactions.
- **SMS alerts** are sent by TMS Companion. A new message is stored and classified in the same request. `POST /sms/parse` reclassifies one stored SMS.

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
3. Matching messages are sent to `POST /sms/ingest_and_parse`.
4. A new SMS: the same request inserts `raw_sms_data`, classifies, writes `transactions_sms` when the classification has a ledger, sets `processing_status`, then commits. A duplicate upload leaves both tables unchanged.
5. `GET /sms/transactions` lists SMS ledger rows and manual ledger rows. The web **SMS** page shows the raw messages and that ledger.

Gmail filters and Android filters are separate. Gmail `GET /transactions` does not include SMS.

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

- `POST /sms/ingest_and_parse` accepts `message_id`, `sender`, `body`, `received_at`, and `device_id`.
- `body` is required. The other fields are optional at the API boundary.
- When `SMS_INGEST_TOKEN` is configured, the request must include the same value in `X-TrackMySpend-Token`.
- The API hashes the sender, body, and device ID (`content_hash`). A unique index prevents retries and live-vs-inbox reuploads from creating duplicate rows. `received_at` is stored but not part of the hash.
- A new SMS: the same request inserts `raw_sms_data`, classifies, writes `transactions_sms` when the classification has a ledger, sets `processing_status`, then commits. A duplicate upload leaves both tables unchanged.
- `GET /sms` returns the stored raw SMS records ordered by `received_at` (newest first), not by insert `id`.
- `GET /sms/transactions` lists the ledger. Gmail `GET /transactions` does not include SMS.

### SMS ledger

`transactions_sms` holds SMS ledger rows and manual ledger rows. An SMS ledger row comes from one raw SMS. A manual ledger row is typed in: `raw_sms_id` is null and `template_name` is `manual`. The list includes both. A manual row has no `sender` or `device_id`. These routes do not use `SMS_INGEST_TOKEN`.

`kind` is `debit`, `credit`, `bill_reminder`, or `balance`. `amount_paisa` is required except on a bill reminder. A balance is the available amount in an account, not money received or spent. Blank `instrument`, `account_mask`, `counterparty`, and `reference` are stored as null.

A `balance_alert` raw SMS is stored as kind `balance`: the available amount, the account mask as the SMS writes it, and instrument `account`. The date in the message stays on the raw SMS. Other info messages, and ignore messages, do not write a ledger row. A raw SMS already stored is unchanged until `POST /sms/parse` runs for that id.

`created_at` and `updated_at` are server time. The client does not send them. On insert they match. A later update moves only `updated_at`.

`POST /sms/transactions` creates a manual row. Send `kind` (`debit`, `credit`, `bill_reminder`, or `balance`) and, except for a bill reminder, `amount_paisa`. `instrument`, `account_mask`, `counterparty`, `reference`, and `sms_received_at` are optional. Omit `sms_received_at` and it matches `created_at`. The response is the saved row.

`PATCH /sms/transactions/{id}` changes those same fields on either row type. Omitted fields stay. Null clears an optional text field. `kind` and `sms_received_at` cannot be null. `raw_sms_id`, `template_name`, and `created_at` cannot be changed, and any other field is rejected. An empty body is 400. A missing id is 404. The response is the saved row.

`DELETE /sms/transactions/{id}` removes the ledger row and returns `{"status": "deleted", "id": <id>}`. The raw SMS and its processing status stay as they are. A later parse of that raw SMS can insert a new SMS ledger row. A deleted manual row stays deleted.

`POST /sms/parse` takes `{"raw_sms_id": <id>}`. An unknown id is 404. The response is `raw_sms_id`, `processing_status`, and `transaction` (the ledger row, or null).

When that classification has a ledger, the SMS ledger row is updated in place: same `id`, same `created_at`. `kind`, `amount_paisa`, `instrument`, `account_mask`, `counterparty`, `reference`, `template_name`, and `sms_received_at` are replaced. `sms_received_at` goes back to the phone's time. `updated_at` becomes server time. If no ledger row exists yet, one is inserted. When the classification has no ledger, that SMS ledger row is deleted. Hand edits on that row do not survive this call. Manual ledger rows are never involved. There is no bulk reparse.

See [TMS Companion documentation](mobile_companion_app/README.md) for Android features, setup, delivery retries, and updates.

### Web UI

The frontend is plain HTML, CSS, and JavaScript. It has seven pages:

- **Home:** API status and totals for accounts, filters, mail, SMS, transactions, and events.
- **Accounts:** connect, list, sync, and remove Gmail accounts; sync all accounts or parse pending mail.
- **Filters:** add and delete Gmail sender filters.
- **Mail:** inspect raw matching Gmail alerts and processing states.
- **SMS:** inspect raw messages from TMS Companion and the SMS ledger.
- **Transactions:** view amounts parsed from Gmail. This list does not include SMS.
- **Logs:** view important application events.

The sidebar's **API base** field can temporarily point the UI at another API server. Its default comes from `API_PUBLIC_BASE` through generated file `frontend/js/env.js`.

### Logging

File logs, the web Logs page, the phone outbox, and Android logcat are separate. See [Logs](#logs).

### Companion updates

- `GET /app/update.json` serves `releases/companion/update.json`. `apk_url` in that file is a path; the response prefixes `API_PUBLIC_BASE`.
- `GET /releases/{filename}` serves APK files from `releases/companion/`.
- A missing or malformed manifest produces a safe fallback and an event-log entry.

## Logs

Four places hold logs. They are not copies of each other.

| Place | What it is for |
| --- | --- |
| `logs/app.log` and the API console | Debugging the API process |
| `app_event_logs`, shown on the web **Logs** page | A readable history of state changes |
| Phone file `outbox_messages.json`, shown on the companion **Log** tab | Each SMS the phone queued, plus a failed backfill |
| Android logcat, tag `SmsReceiver` | A crash while the phone is saving or queueing an SMS |

`sync_runs` stores each Gmail sync's counts in PostgreSQL. It is not shown on the Logs page. The sync event message on that page already includes seen, inserted, skipped, and failed.

Nothing in any of these logs includes an SMS body, a mail body, an OAuth code, a token, or `ENCRYPTION_KEY`.

### File log

`src/core/logging.py` configures the root logger when the API starts. Each line goes to the console and to `logs/app.log`. The file rotates at `LOG_FILE_MAX_BYTES` (default 2 MB) and keeps `LOG_FILE_BACKUP_COUNT` backups (default 3). Timestamps are IST. `LOG_LEVEL` defaults to `INFO`. `LOG_JSON=true` writes one JSON object per line (`ts`, `level`, `name`, `message`, and `exc` when there is a traceback). Otherwise the line is `time | level | logger name | message`. `LOG_DIR` defaults to `logs`.

`main.py` turns Uvicorn's own access log off. The API middleware writes one line per HTTP request instead: method, path, status, duration in milliseconds, client address, and request id. A supplied `X-Request-ID` is kept. Otherwise the API generates one and returns it on the response. A crashed request is logged with the traceback.

At INFO you also get startup and shutdown, SMS ingest, Gmail sync, mail parse, OAuth failures, filter changes, poller start and stop, and migration. Idle poller ticks are silent. A tick that throws is logged here and not in `app_event_logs`, because that database write would be down too.

Warnings include a rejected SMS token, an empty `SMS_INGEST_TOKEN` at startup (ingest is open), an unmatched SMS, a partial mail parse, a stale Gmail history id, a Gmail date header that did not parse, a rejected OAuth state, and a missing companion manifest. The OAuth warning is the reason only. The code and the state are not logged. A bad Gmail token decrypt is the existing sync-failed line with `reason=token_decrypt_failed`.

A successful companion update check is DEBUG, so it does not appear at the default level. Manifest failures stay at warning or error.

### Activity log

`insert_event_log` writes `app_event_logs`. The write is best-effort: if it fails, the real operation still commits and the failure is written to `logs/app.log`.

`GET /logs` returns the newest rows. `limit` defaults to 50 and cannot exceed 200. `offset` pages through them. The web Logs page shows when, severity, source, event type, message, and context. Context is one `key=value` line per field. An empty context cell is blank.

These events are written:

| Event | When |
| --- | --- |
| `sms.ingest_accepted` | A new SMS was stored and classified. Warning when status is `unmatched`. The message includes `processing_status`, `template`, and `reason` (`none`, `no_template`, or `amount_unparsed`). |
| `sms.ingest_duplicate` | The upload matched an existing `content_hash`. No new `raw_sms_data` row. The message names the existing row id. |
| `sms.ingest_failed` | Insert or classification threw. The message includes the raw id when the insert had already returned one. |
| `gmail.sync_started` | A sync run started. |
| `gmail.sync_completed` | Sync finished or was skipped because there are no sender filters. The done message includes seen, inserted, skipped, and failed. |
| `gmail.sync_failed` | Sync threw. The message includes the error, or `reason=token_decrypt_failed`. |
| `parse.completed` | A mail parse batch finished. Warning when some rows failed. The message lists up to 20 failed raw-mail ids, then `+N`. |
| `parse.failed` | Every claimed mail row failed. |
| `gmail.connected` | A Gmail account was connected. |
| `gmail.removed` | A Gmail account was removed. |
| `filter.added` | A Gmail sender filter was added. |
| `filter.deleted` | A Gmail sender filter was deleted. The message includes the pattern. |
| `companion.manifest_missing` | `releases/companion/update.json` is not there. Warning. A fallback manifest is still served. |
| `companion.manifest_unreadable` | That file exists and is not valid JSON. Error. |
| `backfill.after_server_save`, `backfill.on_open`, `backfill.manual` | The phone posts `POST /logs/event` after a backfill that enqueued at least one SMS. Warning when the scan hit its row cap. |

These are not activity events. The HTTP line in `app.log` is enough:

- `GET /sms/latest-received-at` (the phone watermark)
- A companion update check that succeeds
- A backfill that enqueued nothing and had no error
- List endpoints, health, and an idle poller tick

A phone backfill count and `raw_sms_data` can differ by the duplicate events. The phone counts an outbox row when sender, body, and received time are new. The server hash is sender, body, and device id, so a second upload of the same text with a different time is `sms.ingest_duplicate` and does not insert. To find that pair, list the events, take the duplicate's `id` in the message (the existing raw row), and find the `sms.ingest_accepted` event with the same context id. The two `message_id` values are the two rows in a phone export.

### Phone outbox

TMS Companion keeps `outbox_messages.json` on the device. The Log tab lists it. Each SMS row has message id, sender, body, received time, status (`pending`, `sending`, `sent`, `failed`, `ignored`), attempt count, last error, server URL, HTTP code, and acked time. An OTP is stored with a redacted body and status `ignored`.

A failed backfill (no SMS permission, no server, or the watermark fetch failed) writes one row: sender `backfill`, body `backfill failed`, and the error in `lastError`. The same error is not written again. That row does not move the SMS catch-up cursor, and retry does not upload it. The home screen's failed count does not include it.

Exporting that file and counting rows counts the phone outbox, not `raw_sms_data`.

### Logcat

`SmsReceiver` writes `Log.e` with tag `SmsReceiver` when insert or enqueue throws. The line includes the sender and the stack trace. It does not include the SMS body. Successful delivery is not written to logcat.

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

- `POST /sms/ingest_and_parse` — receive an SMS from TMS Companion. A new row is stored and classified before commit. A duplicate leaves both tables unchanged.
- `POST /sms/parse` — reclassify one raw SMS by `raw_sms_id`. Updates that ledger row in place, inserts one if it was missing, or deletes it when the classification has no ledger.
- `POST /sms/transactions` — create a manual ledger row. `template_name` is `manual` and `raw_sms_id` is null.
- `PATCH /sms/transactions/{id}` — update ledger fields on either row type. `raw_sms_id`, `template_name`, and `created_at` stay as they are. `updated_at` becomes server time.
- `DELETE /sms/transactions/{id}` — delete a ledger row. The raw SMS is left as it is.
- `GET /sms` — list raw SMS messages.
- `GET /sms/transactions` — list the SMS ledger. Gmail `GET /transactions` does not include these rows.
- `GET /logs` — list application events. See [Logs](#logs).
- `POST /logs/event` — phone posts a backfill event. Same token header as SMS ingest when `SMS_INGEST_TOKEN` is set.

### Android updates

- `GET /app/update.json` — return the Android update manifest. A path in `apk_url` is prefixed with `API_PUBLIC_BASE`.
- `GET /releases/{filename}` — download a published APK.

`GET /mails`, `GET /transactions`, `GET /sms`, `GET /sms/transactions`, and `GET /logs` accept `limit` and `offset`. The default limit is 50 and the maximum is 200.

## Project layout

```text
src/accounts/                     Gmail OAuth and connected accounts
src/filters/                      Gmail sender filters
src/mail/                         Gmail sync, polling, storage, and parsing
src/sms/                          SMS ingest, one-row parse, and the SMS ledger
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
- `SMS_INGEST_TOKEN` — optional shared token required by `POST /sms/ingest_and_parse`.
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

Only SMS ingestion has shared-token protection inside this application. If the API is exposed publicly, protect the remaining routes at the network or proxy layer. Any proxy access policy must still allow the companion to reach `/health`, `/sms/ingest_and_parse`, `/app/update.json`, and `/releases/`.

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
