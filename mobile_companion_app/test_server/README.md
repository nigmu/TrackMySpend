# SMS ingest test server

FastAPI server that receives SMS JSON from the companion app and stores rows in Postgres (`raw_sms`).

Endpoints:

- `GET /health` — liveness check
- `POST /sms/ingest` — `{sender?, body, received_at?, device_id?}`
- `GET /app/update.json` — OTA manifest (`version_code`, `version_name`, `apk_url`, optional `changelog`)
- `GET /releases/{filename}` — static APK files (e.g. `/releases/companion-1.1.apk`)

## Prerequisites

- Python 3.11+ (or any version your main TrackMySpend app uses)
- Postgres running and reachable (same `DATABASE_URL` shape as the main app)

The `raw_sms` table is created on startup (`CREATE TABLE IF NOT EXISTS`).

## Setup

```bash
cd mobile_companion_app/test_server
cp .env.example .env          # Windows: copy .env.example .env
```

Edit `.env` if your Postgres credentials differ:

```
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/trackmyspend
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Start the server

Bind on all interfaces so a phone on your LAN can reach it:

```bash
uvicorn main:app --host 0.0.0.0 --port 2005
```

Do **not** use `127.0.0.1` as the URL in the Android app — use your machine's LAN IP, e.g. `http://192.168.1.63:2005`.

## Verify

Health check (from the server machine):

```bash
curl http://127.0.0.1:2005/health
# {"status":"ok"}
```

Test ingest:

```bash
Invoke-RestMethod -Method POST -Uri "http://192.168.x.x:2005/sms/ingest" `
  -ContentType "application/json" `
  -Body '{"sender":"VM-HDFCBK","body":"Rs.100 spent","received_at":"2026-09-02T20:00:00+05:30","device_id":"test"}'
# {"status":"ok","id":1}
```

`body` is required. `sender`, `received_at`, and `device_id` are optional.

From another device on the LAN, replace `127.0.0.1` with the server's IP to confirm firewall/routing.

## Connect the Android app

1. Start this server with `--host 0.0.0.0`.
2. In the companion app **Servers** tab, add `http://<your-lan-ip>:2005`.
3. Tap **Test** — expect `OK: {"status":"ok"}`.

See `../android_app/README.md` for building and installing the app.

## OTA updates (companion app)

The server hosts a JSON manifest and APK files for **manual** in-app updates (toolbar ☰ on the phone). Nothing is pushed automatically.

| Path | Source |
|------|--------|
| `GET /app/update.json` | Reads `releases/update.json` on each request (starter file ships with `version_code` 1) |
| `GET /releases/{filename}` | `StaticFiles` on the `releases/` directory |

### Manifest

Edit `releases/update.json`:

```json
{
  "version_code": 2,
  "version_name": "1.1",
  "apk_url": "http://192.168.1.63:2005/releases/companion-1.1.apk",
  "changelog": "- Fixed filter matching"
}
```

| Field | Required | Notes |
|-------|----------|--------|
| `version_code` | yes | Integer. App compares this to the installed `versionCode`. Same → "Up to date". Higher or lower both prompt (upgrade / downgrade). |
| `version_name` | yes | Shown in the dialog. |
| `apk_url` | yes | **Full URL** the phone will GET. Host must be reachable from the phone — same LAN IP, Tailnet IP, or HTTPS host you put in the app's manifest URL. A LAN `apk_url` will fail if the phone only has the Tailnet path. |
| `changelog` | no | Shown in the update dialog when non-empty. |

Examples (replace with your machine's addresses):

```
http://192.168.1.63:2005/app/update.json
http://192.168.1.63:2005/releases/companion-1.1.apk

http://100.x.x.x:2005/app/update.json
http://100.x.x.x:2005/releases/companion-1.1.apk
```

If `releases/update.json` is missing, the endpoint returns `version_code` 1 and an empty `apk_url`.

### Publish a release

1. Bump `versionCode` / `versionName` in `../android_app/app/build.gradle.kts`.
2. Build APK: `cd ../android_app && .\gradlew.bat assembleDebug` (or `assembleRelease`). Sign with the **same key** as the app already on the phone.
3. Copy the APK to `releases/companion-{version}.apk` (APKs are gitignored).
4. Edit `releases/update.json` — set `version_code`, `version_name`, `apk_url` (matching the host the phone can reach), optional `changelog`.
5. On the phone: ☰ → **Update manifest URL…** → `http://<reachable-ip>:2005/app/update.json`.
6. ☰ → **Check for updates** → confirm → allow **Install unknown apps** if prompted.

Verify from the server machine:

```bash
curl http://127.0.0.1:2005/app/update.json
```

While `version_code` matches the installed app, the phone shows "Up to date".

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `DATABASE_URL` not set | Create `.env` from `.env.example` |
| Connection refused from phone | Use `--host 0.0.0.0`; allow port 2005 through the firewall |
| Postgres error on startup | Confirm Postgres is running and the database exists |
| Manifest OK, APK download fails | `apk_url` host/IP must match what the phone can reach; APK file must exist under `releases/` |
| 404 on `/releases/...` | Copy the APK into `releases/` (filename must match `apk_url`) |
