package com.trackmyspend.companion

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.Settings
import android.provider.Telephony
import androidx.core.content.ContextCompat
import org.json.JSONObject

enum class BackfillSource {
    AFTER_SERVER_SAVE,
    ON_OPEN,
    MANUAL,
}

data class BackfillResult(
    val source: BackfillSource,
    val enqueued: Int = 0,
    val scanned: Int = 0,
    val hitCap: Boolean = false,
    val watermarkUsed: Boolean = false,
    val skipped: Boolean = false,
    val error: String? = null,
)

object InboxBackfill {

    fun run(context: Context, source: BackfillSource): BackfillResult {
        val appContext = context.applicationContext
        val store = MessageStore(appContext)
        if (ContextCompat.checkSelfPermission(appContext, Manifest.permission.READ_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return fail(store, source, "SMS permission not granted")
        }

        val prefs = PrefsStore(appContext)
        val lookbackHours = prefs.getBackfillLookbackHours()
        val maxRows = prefs.getBackfillMaxRows()
        val servers = prefs.getServers()

        if (source == BackfillSource.ON_OPEN && store.isEmpty()) {
            return BackfillResult(source = source, skipped = true)
        }

        val cursor = resolveCursor(store, servers, appContext, lookbackHours, source)
            ?: return fail(
                store,
                source,
                if (servers.isEmpty()) "No server configured" else "Watermark fetch failed on all servers",
                watermarkUsed = store.isEmpty(),
            )

        val sinceMillis = cursor.sinceMillis
        var enqueued = 0
        var scanned = 0
        var hitCap = false

        appContext.contentResolver.query(
            Telephony.Sms.Inbox.CONTENT_URI,
            arrayOf(
                Telephony.Sms.ADDRESS,
                Telephony.Sms.BODY,
                Telephony.Sms.DATE,
            ),
            "${Telephony.Sms.DATE} >= ?",
            arrayOf(sinceMillis.toString()),
            "${Telephony.Sms.DATE} DESC",
        )?.use { cursorRows ->
            val addressIdx = cursorRows.getColumnIndexOrThrow(Telephony.Sms.ADDRESS)
            val bodyIdx = cursorRows.getColumnIndexOrThrow(Telephony.Sms.BODY)
            val dateIdx = cursorRows.getColumnIndexOrThrow(Telephony.Sms.DATE)
            while (cursorRows.moveToNext()) {
                if (scanned >= maxRows) {
                    hitCap = true
                    break
                }
                scanned++
                val sender = cursorRows.getString(addressIdx)?.trim().orEmpty()
                val body = cursorRows.getString(bodyIdx).orEmpty()
                val receivedAt = cursorRows.getLong(dateIdx)
                if (sender.isEmpty() || body.isEmpty()) continue
                if (!prefs.matchesAnyFilter(sender)) continue
                if (OtpFilter.isOtpSms(body)) {
                    store.insertIgnored(sender, receivedAt)
                    continue
                }
                val message = store.insertIfNew(sender, body, receivedAt) ?: continue
                UploadWorker.enqueue(appContext, message.messageId)
                enqueued++
            }
        }

        val result = BackfillResult(
            source = source,
            enqueued = enqueued,
            scanned = scanned,
            hitCap = hitCap,
            watermarkUsed = cursor.watermarkUsed,
        )
        postBackfillEvent(servers, result, sinceMillis)
        return result
    }

    private fun fail(
        store: MessageStore,
        source: BackfillSource,
        error: String,
        watermarkUsed: Boolean = false,
    ): BackfillResult {
        store.insertBackfillFailure(error)
        return BackfillResult(source = source, watermarkUsed = watermarkUsed, error = error)
    }

    /** Quiet success stays info. An error or a capped scan is a warning. */
    internal fun backfillSeverity(error: String?, hitCap: Boolean): String =
        if (error != null || hitCap) "warning" else "info"

    /** Pure cursor choice for self-check: local max wins when present. */
    internal fun chooseLocalOrLookback(localMaxMillis: Long?, lookbackHours: Int, nowMillis: Long): Long {
        if (localMaxMillis != null) return localMaxMillis
        return nowMillis - lookbackHours * 60L * 60L * 1000L
    }

    private data class Cursor(val sinceMillis: Long, val watermarkUsed: Boolean)

    private fun resolveCursor(
        store: MessageStore,
        servers: List<ServerConfig>,
        context: Context,
        lookbackHours: Int,
        source: BackfillSource,
    ): Cursor? {
        if (!store.isEmpty()) {
            val localMax = store.maxReceivedAtMillis()
                ?: (System.currentTimeMillis() - lookbackHours * 60L * 60L * 1000L)
            return Cursor(sinceMillis = localMax, watermarkUsed = false)
        }
        // Empty outbox: need server watermark (Save / Manual). Open already skipped.
        if (source == BackfillSource.ON_OPEN) {
            return null
        }
        val deviceId = Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ANDROID_ID,
        ).orEmpty()
        when (val fetch = SmsUploader.fetchLatestReceivedAt(servers, deviceId)) {
            is SmsUploader.WatermarkFetch.Failed -> return null
            is SmsUploader.WatermarkFetch.Ok -> {
                val since = fetch.receivedAtMillis
                    ?: (System.currentTimeMillis() - lookbackHours * 60L * 60L * 1000L)
                return Cursor(sinceMillis = since, watermarkUsed = true)
            }
        }
    }

    /** Quiet open-app scans stay off the activity feed. An enqueue or an error still posts. */
    internal fun shouldPostBackfill(enqueued: Int, error: String?): Boolean =
        enqueued > 0 || error != null

    private fun postBackfillEvent(servers: List<ServerConfig>, result: BackfillResult, sinceMillis: Long) {
        if (result.error != null && result.watermarkUsed) {
            // All servers down — cannot POST; phone UI only.
            return
        }
        if (!shouldPostBackfill(result.enqueued, result.error)) return
        val eventType = when (result.source) {
            BackfillSource.AFTER_SERVER_SAVE -> "backfill.after_server_save"
            BackfillSource.ON_OPEN -> "backfill.on_open"
            BackfillSource.MANUAL -> "backfill.manual"
        }
        val context = JSONObject()
            .put("enqueued", result.enqueued)
            .put("scanned", result.scanned)
            .put("hit_cap", result.hitCap)
            .put("watermark_used", result.watermarkUsed)
            .put("since_millis", sinceMillis)
        SmsUploader.postEvent(
            servers,
            eventType,
            "Backfill ${result.source.name.lowercase()} enqueued=${result.enqueued}",
            context,
            backfillSeverity(result.error, result.hitCap),
        )
    }
}
