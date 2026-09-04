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
    val token: String = "",
    val priority: Int,
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

    fun getServers(): List<ServerConfig> {
        val json = prefs.getString(KEY_SERVERS, "[]") ?: "[]"
        val servers = parseServers(json)
        val normalized = serversToJson(servers)
        if (normalized != json) {
            prefs.edit().putString(KEY_SERVERS, normalized).apply()
        }
        return servers
    }

    fun addServer(name: String, url: String, token: String = ""): ServerConfig {
        val trimmedName = name.trim()
        val trimmedUrl = url.trim().trimEnd('/')
        val trimmedToken = token.trim()
        require(trimmedName.isNotEmpty() && trimmedUrl.isNotEmpty()) { "Name and URL are required" }
        val servers = getServers()
        require(servers.size < MAX_SERVERS) { "Only $MAX_SERVERS servers are supported" }
        val server = ServerConfig(
            id = UUID.randomUUID().toString(),
            name = trimmedName,
            url = trimmedUrl,
            token = trimmedToken,
            priority = servers.size + 1,
        )
        saveServers(servers + server)
        return server
    }

    fun updateServer(id: String, name: String, url: String, token: String = "") {
        val trimmedName = name.trim()
        val trimmedUrl = url.trim().trimEnd('/')
        val trimmedToken = token.trim()
        require(trimmedName.isNotEmpty() && trimmedUrl.isNotEmpty()) { "Name and URL are required" }
        saveServers(
            getServers().map {
                if (it.id == id) it.copy(name = trimmedName, url = trimmedUrl, token = trimmedToken) else it
            }
        )
    }

    fun deleteServer(id: String) {
        saveServers(getServers().filterNot { it.id == id }.withNormalizedPriorities())
    }

    fun moveServer(id: String, offset: Int) {
        val servers = getServers().toMutableList()
        val from = servers.indexOfFirst { it.id == id }
        if (from == -1) return
        val to = (from + offset).coerceIn(0, servers.lastIndex)
        if (from == to) return
        val server = servers.removeAt(from)
        servers.add(to, server)
        saveServers(servers.withNormalizedPriorities())
    }

    fun matchesAnyFilter(sender: String): Boolean {
        val upperSender = sender.uppercase()
        return getFilters().any { filter ->
            filter.enabled && upperSender.contains(filter.pattern.uppercase())
        }
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

    private fun List<ServerConfig>.withNormalizedPriorities(): List<ServerConfig> =
        mapIndexed { index, server -> server.copy(priority = index + 1) }

    companion object {
        const val MAX_SERVERS = 3
        private const val PREFS_NAME = "companion_prefs"
        private const val KEY_FILTERS = "sender_filters"
        private const val KEY_SERVERS = "servers"
        private const val KEY_UPDATE_MANIFEST_URL = "update_manifest_url"

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
            val parsed = buildList {
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    add(
                        Triple(
                            ServerConfig(
                                id = obj.getString("id"),
                                name = obj.getString("name"),
                                url = obj.getString("url"),
                                token = obj.optString("token", ""),
                                priority = obj.optInt("priority", i + 1),
                            ),
                            obj.optBoolean("active", false),
                            obj.has("priority"),
                        )
                    )
                }
            }
            val ordered = if (parsed.isNotEmpty() && parsed.none { it.third }) {
                parsed.sortedByDescending { it.second }
            } else {
                parsed.sortedBy { it.first.priority }
            }
            return ordered.take(MAX_SERVERS).mapIndexed { index, item ->
                item.first.copy(priority = index + 1)
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
                        .put("token", server.token)
                        .put("priority", server.priority)
                )
            }
            return array.toString()
        }
    }
}
