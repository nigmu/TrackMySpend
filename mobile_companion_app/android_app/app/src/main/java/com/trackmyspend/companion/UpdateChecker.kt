package com.trackmyspend.companion

import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

data class UpdateManifest(
    val versionCode: Int,
    val versionName: String,
    val apkUrl: String,
    val changelog: String?,
)

sealed class CompareResult {
    data object UpToDate : CompareResult()
    data class UpdateAvailable(val isUpgrade: Boolean, val manifest: UpdateManifest) : CompareResult()
    data class Error(val message: String) : CompareResult()
}

object UpdateChecker {

    private const val APK_FILE_NAME = "companion-update.apk"

    fun fetchManifest(url: String): UpdateManifest {
        val conn = openGet(url.trim())
        val code = conn.responseCode
        val body = readStream(if (code in 200..299) conn.inputStream else conn.errorStream)
        conn.disconnect()
        if (code !in 200..299) {
            throw IllegalStateException("HTTP $code: ${body.ifBlank { "error" }}")
        }
        val json = JSONObject(body)
        return UpdateManifest(
            versionCode = json.getInt("version_code"),
            versionName = json.getString("version_name"),
            apkUrl = json.getString("apk_url"),
            changelog = json.optString("changelog").takeIf { it.isNotBlank() },
        )
    }

    fun compare(installedCode: Long, manifest: UpdateManifest): CompareResult {
        return when {
            manifest.versionCode.toLong() == installedCode -> CompareResult.UpToDate
            manifest.versionCode.toLong() > installedCode ->
                CompareResult.UpdateAvailable(isUpgrade = true, manifest = manifest)
            else ->
                CompareResult.UpdateAvailable(isUpgrade = false, manifest = manifest)
        }
    }

    fun getInstalledVersionCode(context: Context): Long {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            info.longVersionCode
        } else {
            @Suppress("DEPRECATION")
            info.versionCode.toLong()
        }
    }

    fun downloadApk(url: String, cacheDir: File): File {
        val updatesDir = File(cacheDir, "updates").apply { mkdirs() }
        val apkFile = File(updatesDir, APK_FILE_NAME)
        val conn = openGet(url.trim())
        val code = conn.responseCode
        if (code !in 200..299) {
            val err = readStream(conn.errorStream)
            conn.disconnect()
            throw IllegalStateException("HTTP $code: ${err.ifBlank { "error" }}")
        }
        conn.inputStream.use { input ->
            apkFile.outputStream().use { output -> input.copyTo(output) }
        }
        conn.disconnect()
        return apkFile
    }

    fun launchInstall(context: Context, apkFile: File) {
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            apkFile,
        )
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(intent)
    }

    private fun openGet(urlString: String): HttpURLConnection {
        val conn = URL(urlString).openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = 15_000
        conn.readTimeout = 60_000
        return conn
    }

    private fun readStream(stream: java.io.InputStream?): String {
        if (stream == null) return ""
        return BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { it.readText() }.trim()
    }
}
