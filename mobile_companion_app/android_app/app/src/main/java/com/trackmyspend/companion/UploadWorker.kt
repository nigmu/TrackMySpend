package com.trackmyspend.companion

import android.content.Context
import android.provider.Settings
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

class UploadWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {

    override fun doWork(): Result {
        val messageId = inputData.getString(KEY_MESSAGE_ID) ?: return Result.failure()
        val store = MessageStore(applicationContext)
        val message = store.get(messageId) ?: return Result.success()
        if (message.status == DeliveryStatus.SENT || message.status == DeliveryStatus.IGNORED) {
            return Result.success()
        }
        if (message.sender == MessageStore.BACKFILL_SENDER) return Result.success()

        val servers = PrefsStore(applicationContext).getServers()
        if (servers.isEmpty()) {
            store.markFailed(messageId, "No server configured")
            return Result.success()
        }

        store.markSending(messageId)
        val deviceId = Settings.Secure.getString(
            applicationContext.contentResolver,
            Settings.Secure.ANDROID_ID,
        ).orEmpty()
        var lastError = "Upload failed"

        return try {
            SmsUploader.attemptPlan(servers).forEachIndexed { index, server ->
                if (isStopped) throw InterruptedException("Upload stopped")
                val result = SmsUploader.upload(server, message, deviceId)
                store.recordAttempt(
                    messageId = messageId,
                    serverUrl = server.url,
                    error = result.message.takeUnless { result.success },
                    httpCode = result.httpCode,
                )
                if (result.success) {
                    store.markSent(messageId, server.url, result.httpCode)
                    return Result.success()
                }
                lastError = result.message
                retryDelayMillis(index)?.let { Thread.sleep(it) }
            }
            store.markFailed(messageId, lastError)
            Result.success()
        } catch (_: InterruptedException) {
            store.prepareRetry(messageId)
            Result.retry()
        }
    }

    companion object {
        const val TAG = "sms-upload"
        private const val KEY_MESSAGE_ID = "message_id"
        private const val WORK_PREFIX = "sms-upload-"

        fun enqueue(context: Context, messageId: String) {
            enqueue(context, messageId, ExistingWorkPolicy.KEEP)
        }

        fun enqueueAllPending(context: Context) {
            MessageStore(context).recoverPendingIds().forEach { enqueue(context, it) }
        }

        fun retry(context: Context, messageId: String): Boolean {
            if (!MessageStore(context).prepareRetry(messageId)) return false
            enqueue(context, messageId, ExistingWorkPolicy.REPLACE)
            return true
        }

        private fun enqueue(context: Context, messageId: String, policy: ExistingWorkPolicy) {
            val request = OneTimeWorkRequestBuilder<UploadWorker>()
                .setInputData(Data.Builder().putString(KEY_MESSAGE_ID, messageId).build())
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
                .addTag(TAG)
                .build()
            WorkManager.getInstance(context.applicationContext)
                .enqueueUniqueWork("$WORK_PREFIX$messageId", policy, request)
        }

        internal fun retryDelayMillis(attemptIndex: Int): Long? = when (attemptIndex) {
            0 -> 1_000L
            1 -> 2_000L
            else -> null
        }
    }
}
