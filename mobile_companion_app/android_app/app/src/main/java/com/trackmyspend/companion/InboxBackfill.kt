package com.trackmyspend.companion

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.Telephony
import androidx.core.content.ContextCompat

object InboxBackfill {

    // ponytail: 48h window + 200-row cap; widen if force-stop gaps grow longer
    private const val LOOKBACK_MS = 48L * 60 * 60 * 1000
    private const val MAX_ROWS = 200

    fun run(context: Context): Int {
        val appContext = context.applicationContext
        if (ContextCompat.checkSelfPermission(appContext, Manifest.permission.READ_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return 0
        }

        val prefs = PrefsStore(appContext)
        val store = MessageStore(appContext)
        val since = System.currentTimeMillis() - LOOKBACK_MS
        var enqueued = 0

        appContext.contentResolver.query(
            Telephony.Sms.Inbox.CONTENT_URI,
            arrayOf(
                Telephony.Sms.ADDRESS,
                Telephony.Sms.BODY,
                Telephony.Sms.DATE,
            ),
            "${Telephony.Sms.DATE} >= ?",
            arrayOf(since.toString()),
            "${Telephony.Sms.DATE} DESC",
        )?.use { cursor ->
            val addressIdx = cursor.getColumnIndexOrThrow(Telephony.Sms.ADDRESS)
            val bodyIdx = cursor.getColumnIndexOrThrow(Telephony.Sms.BODY)
            val dateIdx = cursor.getColumnIndexOrThrow(Telephony.Sms.DATE)
            var seen = 0
            while (cursor.moveToNext() && seen < MAX_ROWS) {
                seen++
                val sender = cursor.getString(addressIdx)?.trim().orEmpty()
                val body = cursor.getString(bodyIdx).orEmpty()
                val receivedAt = cursor.getLong(dateIdx)
                if (sender.isEmpty() || body.isEmpty()) continue
                if (!prefs.matchesAnyFilter(sender)) continue
                val message = store.insertIfNew(sender, body, receivedAt) ?: continue
                UploadWorker.enqueue(appContext, message.messageId)
                enqueued++
            }
        }
        return enqueued
    }
}
