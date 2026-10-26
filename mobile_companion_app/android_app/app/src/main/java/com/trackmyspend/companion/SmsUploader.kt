package com.trackmyspend.companion

import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.time.OffsetDateTime

object SmsUploader {

    fun upload(server: ServerConfig, message: OutboxMessage, deviceId: String): UploadResult {
        val payload = JSONObject()
            .put("message_id", message.messageId)
            .put("sender", message.sender)
            .put("body", message.body)
            .put("received_at", message.receivedAt)
            .put("device_id", deviceId)
            .toString()
        return postJson("${server.url}/sms/ingest_and_parse", payload, server.token)
    }

    internal fun attemptPlan(servers: List<ServerConfig>): List<ServerConfig> =
        servers.firstOrNull()?.let { primary -> List(PRIMARY_ATTEMPTS) { primary } + servers.drop(1) }
            ?: emptyList()

    fun testHealth(serverUrl: String): Pair<Boolean, String> {
        val url = serverUrl.trim().trimEnd('/')
        if (url.isEmpty()) return false to "URL is empty"
        return try {
            val conn = openGet("$url/health", token = null)
            val code = conn.responseCode
            val body = readStream(if (code in 200..299) conn.inputStream else conn.errorStream)
            conn.disconnect()
            if (code in 200..299) {
                true to (body.ifBlank { "HTTP $code" })
            } else {
                false to "HTTP $code: ${body.ifBlank { "error" }}"
            }
        } catch (e: Exception) {
            false to (e.message ?: e.javaClass.simpleName)
        }
    }

    /**
     * Tries servers in priority order. Success with null = empty DB for this device.
     * Failure = every server failed.
     */
    fun fetchLatestReceivedAt(servers: List<ServerConfig>, deviceId: String): WatermarkFetch {
        if (servers.isEmpty()) {
            return WatermarkFetch.Failed("No server configured")
        }
        var lastError = "Watermark fetch failed"
        for (server in servers) {
            val encoded = URLEncoder.encode(deviceId, Charsets.UTF_8.name())
            val url = "${server.url}/sms/latest-received-at?device_id=$encoded"
            try {
                val conn = openGet(url, server.token)
                try {
                    val code = conn.responseCode
                    val body = readStream(if (code in 200..299) conn.inputStream else conn.errorStream)
                    if (code in 200..299) {
                        val raw = JSONObject(body).optString("received_at", "")
                        if (raw.isBlank() || raw == "null") {
                            return WatermarkFetch.Ok(null)
                        }
                        val millis = OffsetDateTime.parse(raw).toInstant().toEpochMilli()
                        return WatermarkFetch.Ok(millis)
                    }
                    lastError = "HTTP $code: ${body.ifBlank { "error" }}"
                } finally {
                    conn.disconnect()
                }
            } catch (e: Exception) {
                lastError = e.message ?: e.javaClass.simpleName
            }
        }
        return WatermarkFetch.Failed(lastError)
    }

    fun postEvent(
        servers: List<ServerConfig>,
        eventType: String,
        message: String,
        context: JSONObject? = null,
        severity: String = "info",
    ): Boolean {
        if (servers.isEmpty()) return false
        val payload = JSONObject()
            .put("event_type", eventType)
            .put("message", message)
            .put("severity", severity)
            .put("context", context ?: JSONObject())
            .toString()
        for (server in servers) {
            val result = postJson("${server.url}/logs/event", payload, server.token)
            if (result.success) return true
        }
        return false
    }

    private fun postJson(urlString: String, json: String, token: String): UploadResult {
        return try {
            val conn = openPost(urlString, json, token)
            try {
                val code = conn.responseCode
                val body = readStream(if (code in 200..299) conn.inputStream else conn.errorStream)
                if (code in 200..299) {
                    UploadResult(true, body.ifBlank { "HTTP $code" }, code)
                } else {
                    UploadResult(false, "HTTP $code: ${body.ifBlank { "error" }}", code)
                }
            } finally {
                conn.disconnect()
            }
        } catch (e: Exception) {
            UploadResult(false, e.message ?: e.javaClass.simpleName, null)
        }
    }

    private fun openGet(urlString: String, token: String?): HttpURLConnection {
        val conn = URL(urlString).openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = 10_000
        conn.readTimeout = 10_000
        if (!token.isNullOrBlank()) {
            conn.setRequestProperty("X-TrackMySpend-Token", token)
        }
        return conn
    }

    private fun openPost(urlString: String, json: String, token: String): HttpURLConnection {
        val conn = URL(urlString).openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.connectTimeout = 15_000
        conn.readTimeout = 15_000
        conn.doOutput = true
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        if (token.isNotBlank()) {
            conn.setRequestProperty("X-TrackMySpend-Token", token)
        }
        OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(json) }
        return conn
    }

    private fun readStream(stream: java.io.InputStream?): String {
        if (stream == null) return ""
        return BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { it.readText() }.trim()
    }

    data class UploadResult(val success: Boolean, val message: String, val httpCode: Int?)

    sealed class WatermarkFetch {
        data class Ok(val receivedAtMillis: Long?) : WatermarkFetch()
        data class Failed(val error: String) : WatermarkFetch()
    }

    private const val PRIMARY_ATTEMPTS = 3
}
