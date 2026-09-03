# TrackMySpend Companion (Android)

This app listens for SMS and sends matching ones to TrackMySpend on port **2006**.

| | |
|---|---|
| App id | `com.trackmyspend.companion` |
| Oldest Android | 8.0 (API 26) |
| Target Android | 14 (API 34) |
| Version | `1` / `1.0` in `app/build.gradle.kts` |

Use a **real phone**. Emulators do not receive carrier SMS.

The server is the main TrackMySpend API (`python main.py`), not a separate program.

If the phone still has a server URL with port **2005**, change it to **2006**.

## What you need

- [Android Studio](https://developer.android.com/studio)
- JDK **17** — set Gradle JDK in Android Studio settings  
  **Linux / Windows:** **File → Settings → Build, Execution, Deployment → Build Tools → Gradle → Gradle JDK**  
  **macOS:** **Android Studio → Settings** (or **Preferences**), then the same Gradle JDK path
- Android SDK **34** — **Tools → SDK Manager → SDK Platforms**

## Open the project

1. In Android Studio: **File → Open**
2. Choose this folder: `mobile_companion_app/android_app`  
   Do not open the TrackMySpend repo root.
3. Wait until Gradle finishes (`BUILD SUCCESSFUL`).

## Build an APK

**In Android Studio** (Linux, macOS, and Windows)

1. **Build → Generate App Bundle(s) / APK(s) → Generate APK(s)**
2. Click **locate** when the notification appears.

The file is:

```
app/build/outputs/apk/debug/app-debug.apk
```

**Command line — Linux** (from the repo root)

```bash
cd mobile_companion_app/android_app
./gradlew assembleDebug
```

**macOS** — same as Linux.

**Windows** (PowerShell, from the repo root)

```powershell
cd mobile_companion_app\android_app
.\gradlew.bat assembleDebug
```

Same APK path as above.

## Install on the phone

**From Android Studio (easiest)**

1. On the phone: enable **Developer options** and **USB debugging**.
2. Plug in USB and accept the debug prompt.
3. Pick the phone in the device list and press **Run**.

**From a file**

Copy `app-debug.apk` to the phone and open it to install.

## Set up SMS forwarding

1. Allow SMS when the app asks (`RECEIVE_SMS`, `READ_SMS`).
2. **Filters** — add part of the sender name, for example `HDFCBK`.  
   Matching is case-insensitive. These filters are **only on this phone**. They are not the Gmail filters in the website.
3. **Servers** — add a name and the API URL, for example `http://192.168.1.63:2006`
   - Do not add `/sms/ingest` or a trailing `/`. The app adds `/health` and `/sms/ingest` itself.
   - **Ingest token** — only if the server `.env` has `SMS_INGEST_TOKEN`. Type the same value. If the server token is empty, leave this blank.
   - Mark the server **Active**.
4. Tap **Test**. Success looks like `OK: {"status":"ok"}`.
5. **Log** — last 50 uploads, with URL and HTTP status.

HTTP on your home network is allowed on purpose so `http://192.168.x.x:2006` works without HTTPS.

Uploaded SMS appear on the website **SMS** page. Events appear on **Logs**.

## Install an update from the server (optional)

The app never checks for updates on its own.

1. Menu **☰** (left of the title) → **Update manifest URL…**  
   Paste the full URL, for example:

   ```
   http://192.168.1.63:2006/app/update.json
   ```

   You can also use a Tailscale IP. Leave the field empty to clear the saved URL.

2. **☰** → **Check for updates**
   - Same version as installed → “Up to date”
   - Different version → dialog, then download and Android’s installer

If you never set a URL, you will see “Set update manifest URL first”.

The first time, Android may ask to allow **Install unknown apps** for this companion. Allow it or the install will stop.

The new APK must be signed with the **same key** as the app already on the phone.

### How to publish a new APK

1. Increase `versionCode` and `versionName` in `app/build.gradle.kts`.
2. Build with Gradle. Use the same signing key as the installed app.

   **Linux** and **macOS** (from `mobile_companion_app/android_app`):

   ```bash
   ./gradlew assembleDebug
   ```

   Or `./gradlew assembleRelease` for a release build.

   **Windows** (PowerShell):

   ```powershell
   .\gradlew.bat assembleDebug
   ```

3. Copy the APK to `releases/companion/` and name it something like `companion-1.1.apk`  
   APK files are not committed to git.

   **Linux** and **macOS** example:

   ```bash
   cp app/build/outputs/apk/debug/app-debug.apk ../../releases/companion/companion-1.1.apk
   ```

   **Windows** (PowerShell):

   ```powershell
   copy app\build\outputs\apk\debug\app-debug.apk ..\..\releases\companion\companion-1.1.apk
   ```
4. Edit `releases/companion/update.json`:

   ```json
   {
     "version_code": 2,
     "version_name": "1.1",
     "apk_url": "http://192.168.1.63:2006/releases/companion-1.1.apk",
     "changelog": "- what changed"
   }
   ```

   `apk_url` must be an address the **phone** can open (same LAN or same Tailscale). The filename must exist in `releases/companion/`.

5. On the phone: set the manifest URL to `http://<ip>:2006/app/update.json`
6. **Check for updates**

The API serves:

- `GET /app/update.json` → `releases/companion/update.json`
- `GET /releases/<filename>` → files in `releases/companion/`

## If something goes wrong

| What you see | What to try |
|--------------|-------------|
| Gradle sync fails | Install SDK 34. Set Gradle JDK to 17. |
| **Test** fails / connection refused | Phone and PC on the same Wi‑Fi (or Tailscale). API started with host `0.0.0.0`. URL uses port **2006**, not 2005, and not `127.0.0.1` on the phone. |
| SMS never uploads | Check the Filter text. Grant SMS permission. |
| Server returns 401 | Token on the phone must match `SMS_INGEST_TOKEN` on the server. |
| Phone missing in Run | USB debugging on; install the phone’s USB driver if needed. |
| “Set update manifest URL first” | ☰ → **Update manifest URL…** |
| Installer never opens | Allow **Install unknown apps** for this app. |
| APK download fails | `apk_url` must use a host the phone can reach. File must exist under `releases/companion/`. |
| “App not installed” after update | Wrong signing key, or Android blocked a downgrade. Uninstall first, then install again. |
