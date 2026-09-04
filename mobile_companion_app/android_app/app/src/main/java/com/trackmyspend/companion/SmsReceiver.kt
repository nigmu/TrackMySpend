package com.trackmyspend.companion

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import java.util.concurrent.Executors

class SmsReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (Telephony.Sms.Intents.SMS_RECEIVED_ACTION != intent.action) return
        val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return
        if (messages.isEmpty()) return

        val sender = messages.firstOrNull()?.originatingAddress ?: return
        val body = messages.joinToString(separator = "") { it.messageBody ?: "" }
        if (body.isEmpty()) return

        val appContext = context.applicationContext
        val prefs = PrefsStore(appContext)
        if (!prefs.matchesAnyFilter(sender)) return

        val receivedAt = messages.first().timestampMillis
        val pending = goAsync()
        executor.execute {
            try {
                val message = MessageStore(appContext).insert(sender, body, receivedAt)
                UploadWorker.enqueue(appContext, message.messageId)
            } finally {
                pending.finish()
            }
        }
    }

    companion object {
        // ponytail: one thread is enough for tiny file appends before WorkManager takes over
        private val executor = Executors.newSingleThreadExecutor()
    }
}
