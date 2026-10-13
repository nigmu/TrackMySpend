package com.trackmyspend.companion

import android.content.Context
import android.util.AtomicFile
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.UUID

internal val IST: ZoneId = ZoneId.of("Asia/Kolkata")

enum class DeliveryStatus {
    PENDING,
    SENDING,
    SENT,
    FAILED,
    IGNORED,
}

data class OutboxMessage(
    val messageId: String,
    val sender: String,
    val body: String,
    val receivedAt: String,
    val ackedAt: String? = null,
    val status: DeliveryStatus = DeliveryStatus.PENDING,
    val attemptCount: Int = 0,
    val lastError: String? = null,
    val lastServerUrl: String = "",
    val httpCode: Int? = null,
)

class MessageStore(context: Context) {

    private val file = AtomicFile(File(context.applicationContext.filesDir, FILE_NAME))

    /** Returns the new row, or null if sender+body+receivedAt already exists. */
    fun insertIfNew(sender: String, body: String, receivedAtMillis: Long): OutboxMessage? {
        val receivedAt = formatTime(receivedAtMillis)
        synchronized(lock) {
            val messages = read()
            if (messages.any { it.sender == sender && it.body == body && it.receivedAt == receivedAt }) {
                return null
            }
            val message = OutboxMessage(
                messageId = UUID.randomUUID().toString(),
                sender = sender,
                body = body,
                receivedAt = receivedAt,
            )
            write(messages + message)
            return message
        }
    }

    /** Log row only. Body is [OtpFilter.IGNORED_BODY], never the SMS text. */
    fun insertIgnored(sender: String, receivedAtMillis: Long): OutboxMessage? {
        val receivedAt = formatTime(receivedAtMillis)
        synchronized(lock) {
            val messages = read()
            val body = OtpFilter.IGNORED_BODY
            if (messages.any { it.sender == sender && it.body == body && it.receivedAt == receivedAt }) {
                return null
            }
            val message = OutboxMessage(
                messageId = UUID.randomUUID().toString(),
                sender = sender,
                body = body,
                receivedAt = receivedAt,
                status = DeliveryStatus.IGNORED,
            )
            write(messages + message)
            return message
        }
    }

    fun get(messageId: String): OutboxMessage? = synchronized(lock) {
        read().firstOrNull { it.messageId == messageId }
    }

    fun getAll(): List<OutboxMessage> = synchronized(lock) {
        read().asReversed()
    }

    fun isEmpty(): Boolean = synchronized(lock) {
        read().isEmpty()
    }

    /** Max receivedAt as epoch millis, or null if outbox is empty / unparseable. */
    fun maxReceivedAtMillis(): Long? = synchronized(lock) {
        read().mapNotNull { parseTimeMillis(it.receivedAt) }.maxOrNull()
    }

    fun exportJson(): String = synchronized(lock) {
        encodeMessages(read())
    }

    fun markSending(messageId: String) {
        update(messageId) { it.copy(status = DeliveryStatus.SENDING) }
    }

    fun recordAttempt(messageId: String, serverUrl: String, error: String?, httpCode: Int?) {
        update(messageId) {
            it.copy(
                attemptCount = it.attemptCount + 1,
                lastError = error,
                lastServerUrl = serverUrl,
                httpCode = httpCode,
            )
        }
    }

    fun markSent(messageId: String, serverUrl: String, httpCode: Int?) {
        update(messageId) {
            it.copy(
                ackedAt = formatTime(System.currentTimeMillis()),
                status = DeliveryStatus.SENT,
                lastError = null,
                lastServerUrl = serverUrl,
                httpCode = httpCode,
            )
        }
    }

    fun markFailed(messageId: String, error: String) {
        update(messageId) { it.copy(status = DeliveryStatus.FAILED, lastError = error) }
    }

    fun prepareRetry(messageId: String): Boolean {
        var found = false
        update(messageId) {
            if (it.status == DeliveryStatus.IGNORED) {
                it
            } else {
                found = true
                it.copy(status = DeliveryStatus.PENDING, lastError = null, httpCode = null)
            }
        }
        return found
    }

    fun recoverPendingIds(): List<String> = synchronized(lock) {
        val messages = read()
        val recovered = messages.map {
            if (it.status == DeliveryStatus.SENDING) it.copy(status = DeliveryStatus.PENDING) else it
        }
        if (recovered != messages) write(recovered)
        recovered.filter { it.status == DeliveryStatus.PENDING }.map { it.messageId }
    }

    private fun update(messageId: String, transform: (OutboxMessage) -> OutboxMessage) {
        synchronized(lock) {
            val messages = read()
            val index = messages.indexOfFirst { it.messageId == messageId }
            if (index == -1) return
            write(messages.toMutableList().apply { this[index] = transform(this[index]) })
        }
    }

    private fun read(): List<OutboxMessage> {
        if (!file.baseFile.exists()) return emptyList()
        val text = file.openRead().bufferedReader(Charsets.UTF_8).use { it.readText() }
        return decodeMessages(text)
    }

    private fun write(messages: List<OutboxMessage>) {
        val output = file.startWrite()
        try {
            output.write(encodeMessages(messages).toByteArray(Charsets.UTF_8))
            file.finishWrite(output)
        } catch (error: Throwable) {
            file.failWrite(output)
            throw error
        }
    }

    companion object {
        private const val FILE_NAME = "outbox_messages.json"
        private val lock = Any()
        private val timeFormatter: DateTimeFormatter = DateTimeFormatter.ISO_OFFSET_DATE_TIME

        fun formatTime(timestampMillis: Long): String = timeFormatter.format(
            ZonedDateTime.ofInstant(Instant.ofEpochMilli(timestampMillis), IST)
        )

        fun parseTimeMillis(iso: String): Long? = runCatching {
            ZonedDateTime.parse(iso, timeFormatter).toInstant().toEpochMilli()
        }.getOrNull()

        internal fun encodeMessages(messages: List<OutboxMessage>): String {
            val array = JSONArray()
            messages.forEach { array.put(it.toJson()) }
            return array.toString()
        }

        internal fun decodeMessages(json: String): List<OutboxMessage> {
            val array = JSONArray(json)
            return buildList {
                for (index in 0 until array.length()) add(array.getJSONObject(index).toOutboxMessage())
            }
        }

        private fun OutboxMessage.toJson(): JSONObject = JSONObject()
            .put("messageId", messageId)
            .put("sender", sender)
            .put("body", body)
            .put("receivedAt", receivedAt)
            .put("ackedAt", ackedAt ?: JSONObject.NULL)
            .put("status", status.name.lowercase())
            .put("attemptCount", attemptCount)
            .put("lastError", lastError ?: JSONObject.NULL)
            .put("lastServerUrl", lastServerUrl)
            .put("httpCode", httpCode ?: JSONObject.NULL)

        private fun JSONObject.toOutboxMessage(): OutboxMessage = OutboxMessage(
            messageId = getString("messageId"),
            sender = getString("sender"),
            body = getString("body"),
            receivedAt = getString("receivedAt"),
            ackedAt = nullableString("ackedAt"),
            status = DeliveryStatus.valueOf(getString("status").uppercase()),
            attemptCount = optInt("attemptCount", 0),
            lastError = nullableString("lastError"),
            lastServerUrl = optString("lastServerUrl", ""),
            httpCode = if (has("httpCode") && !isNull("httpCode")) getInt("httpCode") else null,
        )

        private fun JSONObject.nullableString(key: String): String? =
            if (has(key) && !isNull(key)) getString(key) else null
    }
}
