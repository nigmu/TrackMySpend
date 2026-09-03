# SMS companion

This Android app reads SMS on a **real phone** and sends matching messages to the TrackMySpend API.

The API is the main app (`python main.py` on port **2006**). There is no second SMS server.

Emulators do not get carrier SMS. Use a physical phone.

## What happens

1. An SMS arrives on the phone.
2. The app checks **Filters** on the phone (for example `HDFCBK`). This is **not** the Gmail filter list in the web UI.
3. If it matches, the app posts JSON to `http://<your-server>:2006/sms/ingest`.
4. The server stores it in `raw_sms_data`.
5. You can see it on the web **SMS** page (port 2007).

If the same message is sent twice, the server keeps one row.

## Start here

Activate the TrackMySpend venv first (see [../README.md](../README.md)). Commands are **Linux first**; **macOS** is the same; **Windows** is noted if it differs.

### 1. Run the TrackMySpend API

From the **repo root**:

**Linux** and **macOS**

```bash
source .venv/bin/activate
python -m src.db.migrate
python main.py
```

**Windows** (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.db.migrate
python main.py
```

From the phone, the URL must be a LAN (or Tailscale) address, not `127.0.0.1`.

Check from a PC on the same network:

```
http://<server-ip>:2006/health
```

You should see `{"status":"ok"}`.

### 2. Install the Android app

See [android_app/README.md](android_app/README.md) for Android Studio, USB install, or APK install.

Open the folder `mobile_companion_app/android_app` in Android Studio, not the whole repo.

### 3. Set up the phone

1. Allow SMS permissions when asked.
2. **Filters** tab — add a sender pattern, for example `HDFCBK`.
3. **Servers** tab — add a name and URL like `http://192.168.1.63:2006`
   - No path. No slash at the end.
   - Turn **Active** on.
   - Tap **Test**. You want `OK: {"status":"ok"}`.
4. If the server `.env` has `SMS_INGEST_TOKEN`, type the same token in the server dialog on the phone. If that env var is empty, leave the token blank.

### 4. Confirm it worked

- Phone **Log** tab — last 50 send attempts (URL and HTTP status).
- Web UI **SMS** page — the message body.
- Web UI **Logs** page — events like `sms.ingest_accepted`.

If an old phone still uses port **2005**, change the server URL to **2006**.

## App updates (optional)

The app does **not** check for updates by itself. You tap the menu.

1. Put the APK in `releases/companion/` and edit `releases/companion/update.json` (details in the Android README).
2. On the phone: menu **☰** → **Update manifest URL…** →  
   `http://<server-ip>:2006/app/update.json`
3. **☰** → **Check for updates**

The phone must be able to download the APK URL in that JSON file. Use the same kind of address the phone uses for SMS (LAN vs Tailscale).

The new APK must be signed with the **same key** as the app already installed. Android may ask to allow installing from this app.

Full steps: [android_app/README.md](android_app/README.md).
