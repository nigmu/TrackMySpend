package com.trackmyspend.companion

import android.content.Context
import android.provider.Settings
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

object SmsUploader {

    private val isoFormatter: DateTimeFormatter = DateTimeFormatter.ISO_OFFSET_DATE_TIME

    fun upload(context: Context, sender: String, body: String, receivedAtMillis: Long) {
        val appContext = context.applicationContext
        val prefs = PrefsStore(appContext)
        val server = prefs.getActiveServer()
        val timestamp = isoFormatter.format(
            ZonedDateTime.ofInstant(
                java.time.Instant.ofEpochMilli(receivedAtMillis),
                java.time.ZoneId.systemDefault()
            )
        )

        if (server == null) {
            prefs.appendLog(
                UploadLogEntry(
                    timestamp = timestamp,
                    sender = senderSnippet(sender),
                    success = false,
                    message = "No active server configured",
                )
            )
            return
        }

        val deviceId = Settings.Secure.getString(appContext.contentResolver, Settings.Secure.ANDROID_ID) ?: ""
        val payload = JSONObject()
            .put("sender", sender)
            .put("body", body)
            .put("received_at", timestamp)
            .put("device_id", deviceId)
            .toString()

        val result = postJson("${server.url}/sms/ingest", payload, server.token)
        prefs.appendLog(
            UploadLogEntry(
                timestamp = timestamp,
                sender = senderSnippet(sender),
                success = result.success,
                message = result.message,
                serverUrl = server.url,
                httpCode = result.httpCode,
            )
        )
    }

    fun testHealth(serverUrl: String): Pair<Boolean, String> {
        val url = serverUrl.trim().trimEnd('/')
        if (url.isEmpty()) return false to "URL is empty"
        return try {
            val conn = openGet("$url/health")
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

    private fun postJson(urlString: String, json: String, token: String): UploadResult {
        return try {
            val conn = openPost(urlString, json, token)
            val code = conn.responseCode
            val body = readStream(if (code in 200..299) conn.inputStream else conn.errorStream)
            conn.disconnect()
            if (code in 200..299) {
                UploadResult(true, body.ifBlank { "HTTP $code" }, code)
            } else {
                UploadResult(false, "HTTP $code: ${body.ifBlank { "error" }}", code)
            }
        } catch (e: Exception) {
            UploadResult(false, e.message ?: e.javaClass.simpleName, null)
        }
    }

    private fun openGet(urlString: String): HttpURLConnection {
        val conn = URL(urlString).openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = 10_000
        conn.readTimeout = 10_000
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

    private fun senderSnippet(sender: String): String {
        return if (sender.length <= 24) sender else sender.take(21) + "..."
    }

    private data class UploadResult(val success: Boolean, val message: String, val httpCode: Int?)
}
