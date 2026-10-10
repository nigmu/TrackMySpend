# TMS Companion

TMS Companion is an Android app that reads SMS on a real phone and sends matching messages to the TrackMySpend API.

The API is the main TrackMySpend service (`python main.py`, port **2006**). There is no separate SMS server. Carrier SMS is not available in a normal emulator, so use a physical phone.

- App ID: `com.trackmyspend.companion`
- Current version: `1.5` (`versionCode 6`)
- Minimum Android: 8.0 (API 26)
- Target Android: 14 (API 34)
- Build JDK: 17

## How it works

1. Android sends an SMS broadcast to the app. Multipart messages are joined into one message.
2. The app checks the sender against its local **Filters** list.
3. A matching message is saved to the durable local outbox before any upload starts. An OTP text is not saved. The Log gets a row labeled `OTP ignored` and nothing is uploaded.
4. WorkManager sends it to `POST /sms/ingest` when a network is available.
5. The API stores it in `raw_sms_data` and ignores duplicate deliveries.
6. Delivery details appear in the phone's **Log** tab. Stored messages and server events are available through `GET /sms` and `GET /logs`.

## Features

### SMS capture and filtering

- **Background SMS reception:** `SmsReceiver` handles Android's `SMS_RECEIVED` broadcast, joins multipart messages, and records the sender, body, and received time. An SMS that contains `OTP` and a 6-digit code that is not a `Rs` or `INR` amount is not stored. The outbox row says `OTP ignored`.
- **Sender filters:** matching uses a case-insensitive sender substring. For example, `HDFCBK` matches a sender such as `VM-HDFCBK`. Filters are stored only on the phone and are separate from the Gmail filters in the web app.
- **Missed-message recovery:** catch-up is cursor-based, not a blind 48h rescan.
  - **After saving a server while the outbox is empty** (first install / reinstall): the app GETs `/sms/latest-received-at` for this device (tries servers in priority order), snapshots that time once, then scans the inbox for matching SMS with `DATE >=` that watermark (or the last **X** hours if the DB has no rows). The boundary SMS may re-upload; the server `content_hash` (sender+body+device_id) drops duplicates even when `received_at` differs slightly.
  - **On later opens** (outbox already has rows): scan from the max local outbox `receivedAt` only — no server watermark.
  - **Saving a 2nd/3rd server or editing a server** while the outbox is non-empty does **not** re-run watermark backfill.
  - **Manual Pull SMS** (☰ menu): same shared path (watermark if outbox empty, else local cursor). Use this if watermark GET failed on all servers.
  - **X hours** and **max scan rows** are configurable under ☰ → Backfill settings (defaults 48h / 200). A snackbar warns if the cap is hit.
  - A loading overlay shows while a backfill scan runs (not for live SMS). Backfill events are snackbar’d on the phone and posted to `POST /logs/event` when a server is reachable.

### Reliable delivery

- **Durable outbox:** matching SMS is stored in an atomically written local JSON file. Each entry contains a message ID, sender, body, timestamps, delivery state, attempt count, server, HTTP status, and last error.
- **Delivery states:** every message is marked `pending`, `sending`, `sent`, `failed`, or `ignored`. An interrupted `sending` entry is restored to `pending` when the app recovers. An `ignored` row is an OTP notice and is never uploaded.
- **WorkManager uploads:** each message has a unique background job that waits for network connectivity. Interrupted jobs use WorkManager's exponential backoff.
- **Manual retry:** failed entries show a **Retry** button in the Log tab.

### Servers and requests

- **Up to three servers:** server entries contain a name, base URL, and optional token. They can be added, edited, deleted, and reordered.
- **Ordered failover:** the first server is primary and is tried three times. Other servers are tried once each in priority order.
- **Optional authentication:** when `SMS_INGEST_TOKEN` is set on the API, the same value must be saved with the server entry. It is sent in the `X-TrackMySpend-Token` header.
- **Upload payload:** `POST /sms/ingest` receives `message_id`, `sender`, `body`, `received_at`, and `device_id`.
- **Server test:** the **Test** button calls `GET /health` and displays the response.

LAN URLs such as `http://<host>:2006` are allowed. Do not add `/sms/ingest`, `/health`, or a trailing slash to a server URL; the app adds route paths itself.

### Logs and export

- **Detailed Log tab:** shows all local outbox entries, newest first. It includes the sender, received time, delivery state, attempts, message ID, accepted time, server URL, HTTP status, and error. SMS bodies are not displayed in this screen. An OTP SMS appears as **OTP ignored**, with no message text and no Retry button.
- **JSON export:** **☰ → Export messages JSON** writes the complete outbox, including message bodies, to the phone's Downloads folder. An ignored OTP row exports the text `OTP ignored`, not the SMS.

### API integration

- **SMS ingestion:** `POST /sms/ingest` validates the optional token and writes the message to PostgreSQL table `raw_sms_data`.
- **Server-side deduplication:** the API hashes the sender, body, and device ID. A unique database index prevents upload retries (and PDU vs inbox timestamp skew) from creating extra rows.
- **Operational events:** accepted, duplicate, and failed ingestion events are recorded in `app_event_logs` and returned by `GET /logs`.
- **SMS listing:** `GET /sms` returns paginated raw SMS records for the web SMS page.

### App updates

- **Configurable manifest:** **☰ → Update manifest URL…** saves or clears the update-manifest address.
- **Manual checks only:** the app never checks automatically. **☰ → Check for updates** requests the saved manifest.
- **Upgrade and downgrade detection:** the app compares `version_code`, shows the installed and available versions, includes the changelog, and warns before a downgrade.
- **Update hosting:** `GET /app/update.json` serves `releases/companion/update.json`. `apk_url` there is a path such as `/releases/companion-2.0.2.apk`; the response prefixes `API_PUBLIC_BASE`. APKs under `releases/companion/` are served by `GET /releases/<filename>`.
- **Automatic APK copy:** assembling a debug or release APK automatically copies it to `releases/companion/companion-<version>.apk`.

## API routes

- `GET /health` — test API availability.
- `POST /sms/ingest` — accept a message from the phone.
- `GET /sms/latest-received-at` — max `received_at` for a `device_id` (watermark; requires ingest token when configured).
- `GET /sms` — list stored SMS records.
- `GET /logs` — list operational events.
- `POST /logs/event` — companion backfill / ops events (requires ingest token when configured).
- `GET /app/update.json` — return the companion update manifest. A path in `apk_url` is prefixed with `API_PUBLIC_BASE`.
- `GET /releases/<filename>` — download a published APK.

## Run the API

Activate the TrackMySpend environment first; see the [main README](../README.md).

From the repository root:

**Linux and macOS**

```bash
source .venv/bin/activate
python -m src.db.migrate
python main.py
```

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.db.migrate
python main.py
```

Check `http://localhost:2006/health`. The expected response is:

```json
{"status":"ok"}
```

The phone cannot use the computer's `127.0.0.1`. Use the Cloudflare URL, a Tailscale address, or the computer's LAN address.

## Build the Android app

Install:

- [Android Studio](https://developer.android.com/studio)
- JDK 17, selected as the Gradle JDK in Android Studio
- Android SDK 34

Open `mobile_companion_app/android_app` in Android Studio, not the repository root.

Build through **Build → Generate App Bundle(s) / APK(s) → Generate APK(s)**, or run:

**Linux and macOS**

```bash
cd mobile_companion_app/android_app
./gradlew assembleDebug
```

**Windows PowerShell**

```powershell
cd mobile_companion_app\android_app
.\gradlew.bat assembleDebug
```

The original debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`. The build also copies it to `releases/companion/companion-1.5.apk`.

## Install and configure

Install from Android Studio by enabling USB debugging, connecting the phone, and pressing **Run**. You can also copy the generated APK to the phone and open it.

On the phone:

1. Grant `RECEIVE_SMS` and `READ_SMS` when requested.
2. In **Filters**, add a sender pattern such as `HDFCBK`.
3. In **Servers**, add a base URL without a route or trailing slash:
   - Primary: `http://localhost:2006`
   - Optional backups: Tailscale or `http://<host>:2006`
4. Move the preferred server to the first position.
5. If the API has `SMS_INGEST_TOKEN`, enter the same token. Otherwise leave it blank.
6. Tap **Test**. A successful check displays `OK: {"status":"ok"}`.

If an old installation still uses port **2005**, change it to **2006**.

## Verify delivery

- The phone **Log** tab should show the message as `Sent`.
- The web **SMS** page, backed by `GET /sms`, should show the message body.
- The web **Logs** page, backed by `GET /logs`, should show an event such as `sms.ingest_accepted`.

## Publish and install an update

1. Increase `versionCode` and `versionName` in `android_app/app/build.gradle.kts`.
2. Run `assembleDebug` or `assembleRelease`. The APK is copied automatically to `releases/companion/`.
3. Update `releases/companion/update.json`:

```json
{
  "version_code": 6,
  "version_name": "1.5",
  "apk_url": "/releases/companion-1.5.apk",
  "changelog": "- what changed"
}
```

4. On the phone, set the manifest URL to `http://localhost:2006/app/update.json`.
5. Choose **Check for updates**.

The phone downloads `{API_PUBLIC_BASE}` plus that path, so the API host must be reachable from the phone. The new APK must also use the same signing key as the installed app. Android may ask for permission to install unknown apps.

## Troubleshooting

- **Gradle sync fails:** install SDK 34 and select JDK 17 as the Gradle JDK.
- **Test fails:** confirm that the API is running, the phone can reach the host, and the URL uses port 2006 rather than 2005.
- **SMS is not queued:** grant both SMS permissions and check the sender filter.
- **API returns 401:** make the phone token match `SMS_INGEST_TOKEN`.
- **Upload is failed:** open the Log tab for the HTTP status or error, then use **Retry**.
- **APK download fails:** confirm the served `apk_url` (API host plus the path in `update.json`) points to an existing file the phone can reach.
- **App not installed:** use the same signing key and avoid lowering `versionCode`; Android may require uninstalling before a downgrade.
