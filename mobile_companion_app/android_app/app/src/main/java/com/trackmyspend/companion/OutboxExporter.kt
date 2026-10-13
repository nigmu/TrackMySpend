package com.trackmyspend.companion

import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import java.io.File
import java.io.FileOutputStream
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

object OutboxExporter {

    fun exportToDownloads(context: Context): String {
        val json = MessageStore(context).exportJson()
        val fileName = "tms-outbox-${stamp()}.json"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val values = ContentValues().apply {
                put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
                put(MediaStore.MediaColumns.MIME_TYPE, "application/json")
                put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
            }
            val resolver = context.applicationContext.contentResolver
            val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                ?: error("Could not create Downloads entry")
            resolver.openOutputStream(uri)?.use { it.write(json.toByteArray(Charsets.UTF_8)) }
                ?: error("Could not open Downloads stream")
        } else {
            @Suppress("DEPRECATION")
            val dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
            if (!dir.exists() && !dir.mkdirs()) error("Could not create Downloads folder")
            val file = File(dir, fileName)
            FileOutputStream(file).use { it.write(json.toByteArray(Charsets.UTF_8)) }
        }
        return fileName
    }

    private fun stamp(): String =
        DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss").format(ZonedDateTime.now(IST))
}
