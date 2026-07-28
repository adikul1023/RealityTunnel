package com.overreality.vpn.logging

import android.content.Context
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID

enum class LogLevel { INFO, WARN, ERROR }

class ClientLogger(private val context: Context) {

    private val sessionId: String = UUID.randomUUID().toString().replace("-", "").take(8).uppercase()
    private val logDir: File = File(context.filesDir, "logs").apply { mkdirs() }
    private val logFile: File = File(logDir, "client.log")
    private val lock = Any()
    private val dateFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }

    fun log(level: LogLevel, category: String, message: String, requestId: String? = null) {
        val reqId = requestId ?: UUID.randomUUID().toString().replace("-", "").take(8).uppercase()
        val levelStr = when (level) {
            LogLevel.INFO -> "INFO "
            LogLevel.WARN -> "WARN "
            LogLevel.ERROR -> "ERROR"
        }
        val timestamp = dateFormat.format(Date())
        val sanitized = sanitizeMessage(message)
        val line = "$timestamp [$levelStr] [$category] session=$sessionId request=$reqId $sanitized\n"

        synchronized(lock) {
            try {
                rollLogIfNeeded()
                logFile.appendText(line)
            } catch (e: Exception) {
                // Never crash app due to logging failure
            }
        }
    }

    private fun rollLogIfNeeded() {
        if (logFile.exists() && logFile.length() >= 1024 * 1024) {
            val backupFile = File(logDir, "client.log.1")
            if (backupFile.exists()) {
                backupFile.delete()
            }
            logFile.renameTo(backupFile)
        }
    }

    private fun sanitizeMessage(input: String): String {
        var res = input.replace(Regex("ey[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}"), "[REDACTED_JWT]")
        res = res.replace(Regex("(?i)exchange_token=[^&\\s]+"), "exchange_token=[REDACTED]")
        res = res.replace(Regex("(?i)Bearer\\s+[A-Za-z0-9_\\-\\.]+"), "Bearer [REDACTED]")
        return res
    }
}
