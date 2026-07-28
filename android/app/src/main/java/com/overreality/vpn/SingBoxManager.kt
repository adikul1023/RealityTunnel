package com.overreality.vpn

import android.content.Context
import android.os.ParcelFileDescriptor
import android.system.Os
import android.util.Log
import java.io.File
import java.io.FileDescriptor
import java.io.IOException
import java.util.concurrent.TimeUnit

class SingBoxManager(private val context: Context) {
    private var process: Process? = null
    private var loggerThread: Thread? = null
    private val recentLogs = ArrayDeque<String>()
    private val maxRecentLogs = 40

    /**
     * Start sing-box.
     *
     * @param tunFd  The raw file-descriptor integer of the VpnService TUN interface.
     *               Passing a valid fd causes sing-box to use the already-established
     *               tunnel (fd is dup'd to strip O_CLOEXEC so the child inherits it).
     *               Pass -1 to fall back to the legacy interface_name approach.
     */
    fun start(serverIp: String, tunFd: Int = -1) {
        if (process?.isAlive == true) return

        synchronized(recentLogs) { recentLogs.clear() }

        val binary = ensureBinary()

        try {
            startProcess(binary, serverIp, tunFd, useTunFd = tunFd >= 0)
        } catch (e: IllegalStateException) {
            val unsupportedFd = e.message?.contains("unknown field \"fd\"", ignoreCase = true) == true
            if (tunFd >= 0 && unsupportedFd) {
                Log.w(TAG, "Binary does not support tun.fd; retrying with legacy tun config")
                stop()
                try {
                    startProcess(binary, serverIp, tunFd = -1, useTunFd = false)
                } catch (second: IllegalStateException) {
                    val msg = second.message.orEmpty()
                    val netlinkBanned = msg.contains("netlink socket in Android is", ignoreCase = true)
                    if (netlinkBanned) {
                        throw IllegalStateException(
                            "This sing-box binary is not compatible with unprivileged Android mode. " +
                                "It lacks tun.fd support and legacy mode needs root/netlink. " +
                                "Use SFA or integrate libbox-based Android core.",
                            second
                        )
                    }
                    throw second
                }
            } else {
                throw e
            }
        }
    }

    private fun startProcess(binary: File, serverIp: String, tunFd: Int, useTunFd: Boolean) {
        // Dup the TUN fd so the child process can inherit it.
        // Os.dup() (= libc dup()) does NOT copy O_CLOEXEC, so the new fd is
        // inheritable across ProcessBuilder fork()/exec().
        val dupPfd: ParcelFileDescriptor? = if (useTunFd && tunFd >= 0) dupTunFd(tunFd) else null
        val inheritableFd = dupPfd?.fd ?: -1

        val config = writeConfig(serverIp, inheritableFd, useTunFd)

        Log.d(TAG, "Starting core: ${binary.absolutePath}")
        Log.d(TAG, "Config path: ${config.absolutePath}")
        Log.d(TAG, "Executable flag: ${binary.canExecute()}")
        if (inheritableFd >= 0) Log.d(TAG, "Passing TUN fd $inheritableFd to sing-box")

        val pb = ProcessBuilder(binary.absolutePath, "run", "-c", config.absolutePath)
            .directory(context.filesDir)
            .redirectErrorStream(true)

        process = try {
            val p = pb.start()
            // After fork the child has its own copy; close the parent's dup'd fd.
            dupPfd?.close()
            p
        } catch (e: IOException) {
            dupPfd?.close()
            val msg = e.message.orEmpty()
            if (msg.contains("Permission denied", ignoreCase = true)) {
                throw IllegalStateException(
                    "Permission denied while starting core binary. " +
                        "Clean reinstall and ensure jniLibs/arm64-v8a/libsingbox.so is packaged.",
                    e
                )
            }
            if (msg.contains("Exec format error", ignoreCase = true)) {
                throw IllegalStateException(
                    "Wrong sing-box binary ABI for this device. Use android-arm64 build.",
                    e
                )
            }
            throw e
        }

        loggerThread = Thread {
            process?.inputStream?.bufferedReader()?.useLines { lines ->
                lines.forEach { line ->
                    Log.d(TAG, line)
                    synchronized(recentLogs) {
                        if (recentLogs.size >= maxRecentLogs) recentLogs.removeFirst()
                        recentLogs.addLast(line)
                    }
                }
            }
        }.apply { start() }

        // Fail fast if sing-box exits right after launch (common for invalid config/unsupported fields).
        val exitedEarly = process?.waitFor(1500, TimeUnit.MILLISECONDS) == true
        if (exitedEarly) {
            val code = process?.exitValue()
            throw IllegalStateException(
                "sing-box exited immediately (code=$code). Recent logs:\n${dumpRecentLogs()}"
            )
        }
    }

    fun stop() {
        try {
            process?.destroy()
            process?.waitFor()
        } catch (_: Exception) {
        } finally {
            process = null
        }
    }

    private fun dumpRecentLogs(): String {
        val lines = synchronized(recentLogs) { recentLogs.toList() }
        return if (lines.isEmpty()) "(no logs captured)" else lines.joinToString("\n")
    }

    private fun ensureBinary(): File {
        cleanupLegacyBadPath()

        val outDir = File(context.filesDir, "bin").apply { mkdirs() }
        val binary = File(outDir, "sing-box")

        // Always refresh from assets so app updates pick up a newer core binary.
        try {
            context.assets.open("sing-box").use { input ->
                binary.outputStream().use { output -> input.copyTo(output) }
            }

            // Set wide owner/group/world read + execute; write only for owner.
            binary.setReadable(true, false)
        
            // Preferred location on Android: extracted native libs directory.
            // This avoids noexec restrictions on writable app-data mounts.
            val nativeBinary = File(context.applicationInfo.nativeLibraryDir, "libsingbox.so")
            if (nativeBinary.exists() && nativeBinary.canExecute()) {
                Log.d(TAG, "Using native binary: ${nativeBinary.absolutePath}")
                return nativeBinary
            }
            binary.setExecutable(true, false)
            binary.setWritable(true, true)

            // Enforce POSIX mode when available.
            try {
                Os.chmod(binary.absolutePath, 0x1ED) // 0755
            } catch (_: Exception) {
                // Best effort; Java file flags above already set.
            }
        } catch (e: Exception) {
            throw IllegalStateException(
                "Missing sing-box asset. Add binary to app/src/main/assets/sing-box",
                e
            )
        }

        if (!binary.canExecute()) {
            throw IllegalStateException(
                "Core binary is not executable: ${binary.absolutePath}. " +
                    "Please reinstall app and ensure correct ABI binary is used."
            )
        }

        return binary
    }

    private fun cleanupLegacyBadPath() {
        // Earlier bad extraction patterns could create '/files/ bin/sing-box'.
        val legacyDir = File(context.filesDir, " bin")
        if (legacyDir.exists()) {
            try {
                legacyDir.deleteRecursively()
            } catch (_: Exception) {
            }
        }
    }

    private fun dupTunFd(fdInt: Int): ParcelFileDescriptor? {
        return try {
            val srcFd = FileDescriptor()
            val field = FileDescriptor::class.java.getDeclaredField("descriptor")
            field.isAccessible = true
            field.setInt(srcFd, fdInt)
            ParcelFileDescriptor.dup(srcFd)
        } catch (e: Exception) {
            Log.w(TAG, "Failed to dup TUN fd $fdInt: $e")
            null
        }
    }

    private fun writeConfig(serverIp: String, tunFd: Int = -1, useTunFd: Boolean = false): File {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val uuid = prefs.getString(KEY_UUID, "") ?: ""
        val pubKey = prefs.getString(KEY_PUBLIC_KEY, "") ?: ""
        val sni = prefs.getString(KEY_SNI, "www.microsoft.com") ?: "www.microsoft.com"
        val shortId = prefs.getString(KEY_SHORT_ID, "") ?: ""

        if (uuid.isBlank() || pubKey.isBlank()) {
            throw IllegalStateException("VPN credentials missing. Save UUID/PublicKey in app settings.")
        }

        val template = context.assets.open("config.android.template.json")
            .bufferedReader()
            .use { it.readText() }

        val tunInbound = if (useTunFd && tunFd >= 0) {
            """
            {
              "type": "tun",
              "tag": "tun-in",
              "fd": $tunFd,
              "mtu": 1500,
              "auto_route": false,
              "stack": "system"
            }
            """.trimIndent()
        } else {
            """
            {
              "type": "tun",
              "tag": "tun-in",
              "interface_name": "singbox_android",
              "address": ["10.0.85.2/24"],
              "mtu": 1500,
              "auto_route": true,
              "strict_route": true,
              "stack": "system"
            }
            """.trimIndent()
        }

        val rendered = template
            .replace("{{TUN_INBOUND}}", tunInbound)
            .replace("{{SERVER_IP}}", serverIp)
            .replace("{{VPN_UUID}}", uuid)
            .replace("{{VPN_PUBLIC_KEY}}", pubKey)
            .replace("{{VPN_SNI}}", sni)
            .replace("{{VPN_SHORT_ID}}", shortId)

        val configFile = File(context.filesDir, "config.android.generated.json")
        configFile.writeText(rendered)
        return configFile
    }

    companion object {
        private const val TAG = "OverREALITY-SingBox"
        private const val PREFS = "overreality_prefs"
        const val KEY_UUID = "vpn_uuid"
        const val KEY_PUBLIC_KEY = "vpn_public_key"
        const val KEY_SNI = "vpn_sni"
        const val KEY_SHORT_ID = "vpn_short_id"
    }
}
