package com.trackmyspend.companion

import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object SmsUploader {

    fun upload(server: ServerConfig, message: OutboxMessage, deviceId: String): UploadResult {
        val payload = JSONObject()
            .put("message_id", message.messageId)
            .put("sender", message.sender)
            .put("body", message.body)
            .put("received_at", message.receivedAt)
            .put("device_id", deviceId)
            .toString()
        return postJson("${server.url}/sms/ingest", payload, server.token)
    }

    internal fun attemptPlan(servers: List<ServerConfig>): List<ServerConfig> =
        servers.firstOrNull()?.let { primary -> List(PRIMARY_ATTEMPTS) { primary } + servers.drop(1) }
            ?: emptyList()

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

    data class UploadResult(val success: Boolean, val message: String, val httpCode: Int?)

    private const val PRIMARY_ATTEMPTS = 3
}
