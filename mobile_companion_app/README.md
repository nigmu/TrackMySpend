# SMS companion

Android app that forwards matching SMS to the **main TrackMySpend API** (port **2006**). There is no separate ingest server.

```
phone SMS
  → android_app Filters (local substring match)
  → POST http://<host>:2006/sms/ingest
  → Postgres raw_sms_data
  → UI SMS page (port 2007)
```

```
android_app/          Kotlin Views (Filters / Servers / Log)
  SmsReceiver         match sender, then upload
  SmsUploader         GET {url}/health, POST {url}/sms/ingest
  UpdateChecker       manual OTA (toolbar ☰)
```

OTA files are served by the same API:

| URL (port 2006) | Disk |
|-----------------|------|
| `GET /app/update.json` | `releases/companion/update.json` |
| `GET /releases/{filename}` | `releases/companion/{filename}` |

Use a **real phone**. Emulators do not receive carrier SMS.

Gmail `sender_filters` on the server do **not** control which SMS the phone uploads. Phone filters live only in the Android app.

## Quick start

1. **API** — from the repo root; see [../README.md](../README.md)

   ```bash
   python -m src.db.migrate
   python main.py
   ```

   Listens on `0.0.0.0:2006`. Confirm `GET http://<lan-ip>:2006/health` → `{"status":"ok"}`.

2. **Android app** — [android_app/README.md](android_app/README.md)

   - Open `android_app/` in Android Studio (not the repo root)
   - Run ▶ on a phone, or install `app/build/outputs/apk/debug/app-debug.apk`

3. **On the phone**

   - Grant SMS permissions
   - **Filters** → sender pattern, e.g. `HDFCBK`
   - **Servers** → `http://<lan-ip>:2006` (no path, no trailing slash), mark **Active**, **Test**
   - If `.env` has `SMS_INGEST_TOKEN`, enter the same value in the server dialog (header `X-TrackMySpend-Token`)

JSON posted: `{sender, body, received_at, device_id}`. Retries with the same fields are stored once (`content_hash`).

Check:

- Phone **Log** tab — last 50 upload attempts (URL + HTTP status)
- Web UI **SMS** page — rows in `raw_sms_data`
- Web UI **Logs** page — `sms.ingest_accepted` / `sms.ingest_duplicate`

If an older install still points at port **2005**, change the server URL to **2006**.

## OTA (optional)

Manual only. The app does not check on launch.

1. Copy the APK to `releases/companion/` and edit `releases/companion/update.json`
2. Phone ☰ → **Update manifest URL…** → `http://<reachable-ip>:2006/app/update.json`
3. ☰ → **Check for updates** — dialog only if `version_code` differs

Same signing key as the installed app. Allow **Install unknown apps** when Android asks.

Details: [android_app/README.md](android_app/README.md).
