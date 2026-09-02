# TrackMySpend Companion (Android)

Listens for matching SMS and POSTs them to the TrackMySpend API on port **2006** (`/sms/ingest`).

| | |
|---|---|
| Package / applicationId | `com.trackmyspend.companion` |
| Min SDK | 26 (Android 8.0) |
| Target / compile SDK | 34 |
| versionCode / versionName | `1` / `1.0` (see `app/build.gradle.kts`) |

Use a **real phone**. Emulators do not receive carrier SMS.

The ingest host is the main app (`python main.py`), not a sidecar. If this phone was configured for port **2005**, edit the server URL to **2006**.

## Prerequisites

- [Android Studio](https://developer.android.com/studio)
- JDK **17** — **File → Settings → Build, Execution, Deployment → Build Tools → Gradle → Gradle JDK**
- Android SDK Platform **34** — **Tools → SDK Manager → SDK Platforms**

## Open the project

1. **File → Open**
2. Select this folder (`mobile_companion_app/android_app`), not the repo root.
3. Wait for Gradle sync (`BUILD SUCCESSFUL`).

## Build a debug APK

### Android Studio

1. **Build → Generate App Bundle(s) / APK(s) → Generate APK(s)**
2. Click **locate** on the notification.

```
app/build/outputs/apk/debug/app-debug.apk
```

### Command line (Windows)

```powershell
cd mobile_companion_app\android_app
.\gradlew.bat assembleDebug
```

Same APK path.

## Install

**Android Studio:** enable **Developer options → USB debugging**, connect the phone, Run ▶.

**Manual:** copy `app-debug.apk` to the phone and open it.

## Configure

1. Grant **SMS** (`RECEIVE_SMS`, `READ_SMS`).
2. **Filters** — sender substring, e.g. `HDFCBK` (case-insensitive). These filters are **only on the phone**. They are not the Gmail filters in the web UI.
3. **Servers** — name + URL, e.g. `http://192.168.1.63:2006`
   - No trailing slash or path. The app appends `/health` and `/sms/ingest`.
   - Optional ingest token: must match server `SMS_INGEST_TOKEN` (header `X-TrackMySpend-Token`). Leave empty if the server token is unset.
   - Mark **Active**.
4. **Test** — expect `OK: {"status":"ok"}`.
5. **Log** — last 50 uploads, with target URL and HTTP status.

Cleartext HTTP is allowed (`usesCleartextTraffic`) so LAN `http://192.168.x.x:2006` works.

Ingested rows show on the web UI **SMS** page (`GET /sms`). Events show on **Logs**.

## OTA updates

Manual. Nothing runs on launch. Manifest URL is independent of the SMS server list.

Toolbar **☰**:

| Menu | Behavior |
|------|----------|
| **Update manifest URL…** | Full URL to JSON. LAN, Tailnet, or HTTPS. Empty clears it. |
| **Check for updates** | Same `version_code` → "Up to date". Different → Update/Downgrade, then download + installer. |

If the URL is empty: "Set update manifest URL first".

Examples:

```
http://192.168.1.63:2006/app/update.json
http://100.x.x.x:2006/app/update.json
```

Hosted by the main API from `releases/companion/`:

- `GET /app/update.json`
- `GET /releases/{filename}`

First install of an OTA APK: allow **Install unknown apps** (`REQUEST_INSTALL_PACKAGES`). APK must use the **same signing key** as the app on the phone.

### Publish a release

1. Bump `versionCode` / `versionName` in `app/build.gradle.kts`.
2. `.\gradlew.bat assembleDebug` (or `assembleRelease`), same key as the installed app.
3. Copy APK to `releases/companion/companion-{version}.apk` (APKs are gitignored).
4. Edit `releases/companion/update.json`:

   ```json
   {
     "version_code": 2,
     "version_name": "1.1",
     "apk_url": "http://192.168.1.63:2006/releases/companion-1.1.apk",
     "changelog": "- notes"
   }
   ```

   `apk_url` must be a host the phone can reach (LAN vs Tailnet). Filename must exist under `releases/companion/`.

5. Phone: ☰ → **Update manifest URL…** → `http://<ip>:2006/app/update.json`
6. ☰ → **Check for updates**

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Gradle sync fails | SDK 34; Gradle JDK 17 |
| Test fails / connection refused | Phone and API on the same network; API binds `0.0.0.0:2006`; URL is `:2006` not `:2005` or `127.0.0.1` |
| SMS not forwarded | Filter pattern; SMS permissions |
| Ingest `401` | Server dialog token = `SMS_INGEST_TOKEN` |
| No device in Run | USB debugging; OEM USB drivers |
| "Set update manifest URL first" | ☰ → **Update manifest URL…** |
| Installer does not open | Allow **Install unknown apps** for this app |
| APK download fails | `apk_url` host must match what the phone can reach; file must exist under `releases/companion/` |
| "App not installed" after OTA | Signing key mismatch, or downgrade blocked — uninstall first |
