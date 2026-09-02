package com.trackmyspend.companion

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class SenderFilter(
    val id: String,
    val pattern: String,
    val enabled: Boolean = true,
)

data class ServerConfig(
    val id: String,
    val name: String,
    val url: String,
    val active: Boolean = false,
)

data class UploadLogEntry(
    val timestamp: String,
    val sender: String,
    val success: Boolean,
    val message: String,
)

class PrefsStore(context: Context) {

    private val prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun getFilters(): List<SenderFilter> = parseFilters(prefs.getString(KEY_FILTERS, "[]") ?: "[]")

    fun addFilter(pattern: String): SenderFilter {
        val trimmed = pattern.trim()
        require(trimmed.isNotEmpty()) { "Pattern cannot be empty" }
        val filter = SenderFilter(id = UUID.randomUUID().toString(), pattern = trimmed)
        saveFilters(getFilters() + filter)
        return filter
    }

    fun deleteFilter(id: String) {
        saveFilters(getFilters().filterNot { it.id == id })
    }

    fun getServers(): List<ServerConfig> = parseServers(prefs.getString(KEY_SERVERS, "[]") ?: "[]")

    fun addServer(name: String, url: String): ServerConfig {
        val trimmedName = name.trim()
        val trimmedUrl = url.trim().trimEnd('/')
        require(trimmedName.isNotEmpty() && trimmedUrl.isNotEmpty()) { "Name and URL are required" }
        val servers = getServers()
        val server = ServerConfig(
            id = UUID.randomUUID().toString(),
            name = trimmedName,
            url = trimmedUrl,
            active = servers.isEmpty(),
        )
        saveServers(servers + server)
        return server
    }

    fun updateServer(id: String, name: String, url: String) {
        val trimmedName = name.trim()
        val trimmedUrl = url.trim().trimEnd('/')
        require(trimmedName.isNotEmpty() && trimmedUrl.isNotEmpty()) { "Name and URL are required" }
        saveServers(
            getServers().map {
                if (it.id == id) it.copy(name = trimmedName, url = trimmedUrl) else it
            }
        )
    }

    fun deleteServer(id: String) {
        val remaining = getServers().filterNot { it.id == id }
        if (remaining.isNotEmpty() && remaining.none { it.active }) {
            saveServers(remaining.mapIndexed { index, server -> server.copy(active = index == 0) })
        } else {
            saveServers(remaining)
        }
    }

    fun setActiveServer(id: String) {
        saveServers(getServers().map { it.copy(active = it.id == id) })
    }

    fun getActiveServer(): ServerConfig? = getServers().firstOrNull { it.active }

    fun matchesAnyFilter(sender: String): Boolean {
        val upperSender = sender.uppercase()
        return getFilters().any { filter ->
            filter.enabled && upperSender.contains(filter.pattern.uppercase())
        }
    }

    fun getUploadLog(): List<UploadLogEntry> = parseLog(prefs.getString(KEY_LOG, "[]") ?: "[]")

    fun appendLog(entry: UploadLogEntry) {
        val updated = (listOf(entry) + getUploadLog()).take(MAX_LOG_ENTRIES)
        prefs.edit().putString(KEY_LOG, logToJson(updated)).apply()
    }

    fun getUpdateManifestUrl(): String? {
        val url = prefs.getString(KEY_UPDATE_MANIFEST_URL, null)?.trim().orEmpty()
        return url.ifEmpty { null }
    }

    fun setUpdateManifestUrl(url: String) {
        val trimmed = url.trim()
        prefs.edit().putString(KEY_UPDATE_MANIFEST_URL, trimmed).apply()
    }

    private fun saveFilters(filters: List<SenderFilter>) {
        prefs.edit().putString(KEY_FILTERS, filtersToJson(filters)).apply()
    }

    private fun saveServers(servers: List<ServerConfig>) {
        prefs.edit().putString(KEY_SERVERS, serversToJson(servers)).apply()
    }

    companion object {
        private const val PREFS_NAME = "companion_prefs"
        private const val KEY_FILTERS = "sender_filters"
        private const val KEY_SERVERS = "servers"
        private const val KEY_LOG = "upload_log"
        private const val KEY_UPDATE_MANIFEST_URL = "update_manifest_url"
        private const val MAX_LOG_ENTRIES = 50

        private fun parseFilters(json: String): List<SenderFilter> {
            val array = JSONArray(json)
            return buildList {
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    add(
                        SenderFilter(
                            id = obj.getString("id"),
                            pattern = obj.getString("pattern"),
                            enabled = obj.optBoolean("enabled", true),
                        )
                    )
                }
            }
        }

        private fun filtersToJson(filters: List<SenderFilter>): String {
            val array = JSONArray()
            filters.forEach { filter ->
                array.put(
                    JSONObject()
                        .put("id", filter.id)
                        .put("pattern", filter.pattern)
                        .put("enabled", filter.enabled)
                )
            }
            return array.toString()
        }

        private fun parseServers(json: String): List<ServerConfig> {
            val array = JSONArray(json)
            return buildList {
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    add(
                        ServerConfig(
                            id = obj.getString("id"),
                            name = obj.getString("name"),
                            url = obj.getString("url"),
                            active = obj.optBoolean("active", false),
                        )
                    )
                }
            }
        }

        private fun serversToJson(servers: List<ServerConfig>): String {
            val array = JSONArray()
            servers.forEach { server ->
                array.put(
                    JSONObject()
                        .put("id", server.id)
                        .put("name", server.name)
                        .put("url", server.url)
                        .put("active", server.active)
                )
            }
            return array.toString()
        }

        private fun parseLog(json: String): List<UploadLogEntry> {
            val array = JSONArray(json)
            return buildList {
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    add(
                        UploadLogEntry(
                            timestamp = obj.getString("timestamp"),
                            sender = obj.getString("sender"),
                            success = obj.getBoolean("success"),
                            message = obj.getString("message"),
                        )
                    )
                }
            }
        }

        private fun logToJson(entries: List<UploadLogEntry>): String {
            val array = JSONArray()
            entries.forEach { entry ->
                array.put(
                    JSONObject()
                        .put("timestamp", entry.timestamp)
                        .put("sender", entry.sender)
                        .put("success", entry.success)
                        .put("message", entry.message)
                )
            }
            return array.toString()
        }
    }
}
