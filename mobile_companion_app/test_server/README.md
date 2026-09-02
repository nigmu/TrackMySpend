# SMS ingest test server

FastAPI server that receives SMS JSON from the companion app and stores rows in Postgres (`raw_sms`).

Endpoints:

- `GET /health` — liveness check
- `POST /sms/ingest` — `{sender?, body, received_at?, device_id?}`

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
uvicorn main:app --host 0.0.0.0 --port 9000
```

Do **not** use `127.0.0.1` as the URL in the Android app — use your machine's LAN IP, e.g. `http://192.168.1.63:9000`.

## Verify

Health check (from the server machine):

```bash
curl http://127.0.0.1:9000/health
# {"status":"ok"}
```

Test ingest:

```bash
Invoke-RestMethod -Method POST -Uri "http://192.168.x.x:9000/sms/ingest" `
  -ContentType "application/json" `
  -Body '{"sender":"VM-HDFCBK","body":"Rs.100 spent","received_at":"2026-09-02T20:00:00+05:30","device_id":"test"}'
# {"status":"ok","id":1}
```

`body` is required. `sender`, `received_at`, and `device_id` are optional.

From another device on the LAN, replace `127.0.0.1` with the server's IP to confirm firewall/routing.

## Connect the Android app

1. Start this server with `--host 0.0.0.0`.
2. In the companion app **Servers** tab, add `http://<your-lan-ip>:9000`.
3. Tap **Test** — expect `OK: {"status":"ok"}`.

See `../android_app/README.md` for building and installing the app.

## Troubleshooting


| Problem                       | Fix                                                        |
| ----------------------------- | ---------------------------------------------------------- |
| `DATABASE_URL` not set        | Create `.env` from `.env.example`                          |
| Connection refused from phone | Use `--host 0.0.0.0`; allow port 9000 through the firewall |
| Postgres error on startup     | Confirm Postgres is running and the database exists        |


