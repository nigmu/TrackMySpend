# TrackMySpend Companion (Android)

Kotlin app that listens for matching SMS and POSTs them to a server (`/sms/ingest`).

| | |
|---|---|
| Package | `com.trackmyspend.companion` |
| Min SDK | 26 (Android 8.0) |
| Target SDK | 34 |

Use a **real phone** for SMS. Emulators do not receive carrier messages.

## Prerequisites

- [Android Studio](https://developer.android.com/studio) (recent stable release)
- JDK 17 — **File → Settings → Build, Execution, Deployment → Build Tools → Gradle → Gradle JDK**
- Android SDK Platform **34** — **Tools → SDK Manager → SDK Platforms**

## Open the project

1. **File → Open**
2. Select this folder (`mobile_companion_app/android_app`), not the repo root.
3. Wait for Gradle sync to finish (`BUILD SUCCESSFUL` in the Build tool window).

## Build a debug APK

### Android Studio

1. **Build → Generate App Bundle(s) / APK(s) → Generate APK(s)**
   (Older Studio versions: **Build → Build Bundle(s) / APK(s) → Build APK(s)**)
2. When the notification appears, click **locate**.

Output:

```
app/build/outputs/apk/debug/app-debug.apk
```

### Command line (Windows)

```powershell
cd mobile_companion_app\android_app
.\gradlew.bat assembleDebug
```

Same APK path as above.

## Install on a device

### Run from Android Studio (recommended)

1. Enable **Developer options → USB debugging** on the phone.
2. Connect via USB; accept the debugging prompt.
3. Select the phone in the device dropdown (top toolbar).
4. Click the green **Run ▶** button.

### Manual install

Copy `app-debug.apk` to the phone and open it to install.

## Configure the app

1. Grant **SMS** permissions when prompted (`RECEIVE_SMS`, `READ_SMS`).
2. **Filters** tab → add a sender pattern, e.g. `HDFCBK` (case-insensitive substring of the SMS address).
3. **Servers** tab → add a name and URL, e.g. `http://192.168.1.63:9000`
   - No trailing slash or path — the app appends `/health` and `/sms/ingest`.
   - Mark the server **Active**.
4. Tap **Test** — expect `OK: {"status":"ok"}`.
5. Matching SMS uploads appear on the **Log** tab (last 50 entries).

Cleartext HTTP is allowed (`usesCleartextTraffic`) so LAN URLs like `http://192.168.x.x:9000` work without HTTPS.

## OTA updates

Manual only. The app never checks on launch and never pops a dialog unless you tap **Check for updates** and the manifest `version_code` is different from the installed app.

Toolbar **☰** (left of the title) — independent of SMS server config:

| Menu item | What it does |
|-----------|----------------|
| **Update manifest URL…** | Full URL to a JSON manifest. LAN, Tailnet, or HTTPS. Empty URL is allowed (clears the saved value). |
| **Check for updates** | Fetches that URL. Same `version_code` → Snackbar "Up to date". Different → dialog (optional `changelog`) with **Update** or **Downgrade**, then download + system installer. |

If the URL is not set, **Check for updates** shows "Set update manifest URL first".

Examples:

```
http://192.168.1.63:9000/app/update.json
http://100.x.x.x:9000/app/update.json
```

The first time the installer runs, Android asks to allow **Install unknown apps** for this companion (`REQUEST_INSTALL_PACKAGES`). Allow it or install will not proceed.

The APK must be signed with the **same key** as the installed app (debug keystore to debug, or the same release key). Android may refuse a lower `version_code` unless you uninstall first.

See `../test_server/README.md` to host `update.json` and APKs.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Gradle sync fails | Install SDK 34; set Gradle JDK to 17 |
| Test connection fails | Phone and server must be on the same LAN; server must bind `0.0.0.0`, not `127.0.0.1` |
| SMS not forwarded | Check Filters pattern; confirm SMS permissions are granted |
| No device in Run dropdown | Enable USB debugging; install phone USB drivers if needed |
| "Set update manifest URL first" | ☰ → **Update manifest URL…** |
| Installer does not open | Allow **Install unknown apps** for this app |
| APK download fails | `apk_url` in the manifest must use a host the phone can reach (same IP as the manifest URL) |
| "App not installed" after OTA | Signing key mismatch, or downgrade blocked — uninstall first |

See `../test_server/README.md` for starting the backend.
