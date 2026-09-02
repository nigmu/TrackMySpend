# SMS companion

Phone SMS → FastAPI `POST /sms/ingest` → Postgres `raw_sms`.

```
android_app/          Kotlin Views app (Filters / Servers / Log)
  SmsReceiver         matches sender filters, then uploads
  SmsUploader         GET {url}/health, POST {url}/sms/ingest
test_server/          FastAPI + Postgres
```

Use a **real device** for SMS. Emulators do not receive carrier messages.

## Quick start

1. **Start the test server** — see [test_server/README.md](test_server/README.md)
   ```bash
   cd mobile_companion_app/test_server
   cp .env.example .env          # Windows: copy .env.example .env
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 9000
   ```
2. **Build and install the Android app** — see [android_app/README.md](android_app/README.md)
   - Open `android_app/` in Android Studio
   - **Build → Generate App Bundle(s) / APK(s) → Generate APK(s)**
   - Install on a phone (Run ▶ over USB, or copy `app/build/outputs/apk/debug/app-debug.apk`)
3. **Configure on the phone**
   - Grant SMS permissions
   - **Filters** → add a sender pattern (e.g. `HDFCBK`)
   - **Servers** → add `http://<your-lan-ip>:9000`, mark Active, tap **Test**

Matching SMS are POSTed as JSON `{sender, body, received_at, device_id}`. Upload attempts appear on the **Log** tab (last 50).

## Docs

| Component | README |
|-----------|--------|
| FastAPI ingest server | [test_server/README.md](test_server/README.md) |
| Android companion app | [android_app/README.md](android_app/README.md) |
