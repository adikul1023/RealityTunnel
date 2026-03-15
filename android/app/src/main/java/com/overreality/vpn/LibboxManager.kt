package com.overreality.vpn

import android.content.Context
import android.util.Log
import io.nekohasekai.libbox.CommandServer
import io.nekohasekai.libbox.CommandServerHandler
import io.nekohasekai.libbox.Libbox
import io.nekohasekai.libbox.OverrideOptions
import io.nekohasekai.libbox.PlatformInterface
import io.nekohasekai.libbox.SetupOptions
import io.nekohasekai.libbox.SystemProxyStatus
import java.io.File
import java.util.Locale
import java.util.UUID

class LibboxManager(private val context: Context) {

    // Resolve availability at first access: if libbox.aar is not linked the class won't exist.
    private val available: Boolean by lazy {
        runCatching { Class.forName("io.nekohasekai.libbox.Libbox"); true }.getOrElse { false }
    }

    private var commandServer: CommandServer? = null

    private val commandHandler = object : CommandServerHandler {
        override fun serviceStop() {
            Log.d(TAG, "libbox requested service stop")
        }

        override fun serviceReload() {
            Log.d(TAG, "libbox requested service reload")
        }

        override fun writeDebugMessage(message: String?) {
            Log.d(TAG, message ?: "")
        }

        override fun getSystemProxyStatus(): SystemProxyStatus? = null

        override fun setSystemProxyEnabled(enabled: Boolean) {
            // Not used in this app.
        }
    }

    fun isAvailable(): Boolean = available

    fun start(serverIp: String, platform: PlatformInterface) {
        if (!available) throw IllegalStateException(
            "libbox not available — add libbox.aar to android/app/libs/ and sync Gradle.")

        try {
            ensureLibboxSetup(context)
            val configJson = buildConfigJson(serverIp)
            val server = commandServer ?: Libbox.newCommandServer(commandHandler, platform)
                .also { commandServer = it }
            server.startOrReloadService(configJson, OverrideOptions())
        } catch (t: Throwable) {
            throw IllegalStateException("libbox start failed: ${t.message ?: t::class.java.simpleName}", t)
        }
    }

    fun stop() {
        try {
            commandServer?.closeService()
            commandServer?.close()
        } finally {
            commandServer = null
        }
    }

    // -------------------------------------------------------------------------

    private fun buildConfigJson(serverIp: String): String {
        val prefs   = VpnConfigStore.prefs(context)
        val uuid    = prefs.getString(VpnConfigStore.KEY_UUID,       "")                  ?: ""
        val pubKey  = prefs.getString(VpnConfigStore.KEY_PUBLIC_KEY, "")                  ?: ""
        val sni     = prefs.getString(VpnConfigStore.KEY_SNI,        "www.microsoft.com") ?: "www.microsoft.com"
        val shortId = prefs.getString(VpnConfigStore.KEY_SHORT_ID,   "")                  ?: ""

        if (uuid.isBlank() || pubKey.isBlank())
            throw IllegalStateException("VPN credentials missing — save UUID/PublicKey in app settings.")

        val template = context.assets.open("config.android.template.json")
            .bufferedReader().use { it.readText() }

        // Sing-box log file in external files dir — survives app restarts and can be adb pulled.
        val logFile = (context.getExternalFilesDir(null)
            ?.let { File(it, "libbox") }
            ?: File(context.filesDir, "libbox-working"))
            .also { it.mkdirs() }
            .let { File(it, "sing-box.log").absolutePath }

                // route_address tells libbox to pass "0.0.0.0/1" and "128.0.0.0/1" back through
                // PlatformInterface.openTun() so VpnService.Builder adds them as routes. Without this,
                // no IPv4 routes are added to tun0 and no traffic ever enters the proxy.
        val tunInbound = """
            {
              "type": "tun",
              "tag": "tun-in",
              "address": ["10.0.85.2/24"],
              "mtu": 1500,
              "auto_route": true,
                            "route_address": ["0.0.0.0/1", "128.0.0.0/1"],
              "stack": "mixed",
              "sniff": true
            }""".trimIndent()

        return template
            .replace("{{LOG_PATH}}", logFile)
            .replace("{{TUN_INBOUND}}", tunInbound)
            .replace("{{SERVER_IP}}", serverIp)
            .replace("{{VPN_UUID}}", uuid)
            .replace("{{VPN_PUBLIC_KEY}}", pubKey)
            .replace("{{VPN_SNI}}", sni)
            .replace("{{VPN_SHORT_ID}}", shortId)
    }

    companion object {
        private const val TAG = "OverReality-Libbox"

        @Volatile
        private var setupDone = false

        @Synchronized
        private fun ensureLibboxSetup(context: Context) {
            if (setupDone) return

            val baseDir = File(context.filesDir, "libbox").apply { mkdirs() }
            val workingDir = context.getExternalFilesDir(null)?.let {
                File(it, "libbox").apply { mkdirs() }
            } ?: File(context.filesDir, "libbox-working").apply { mkdirs() }
            val tempDir = File(context.cacheDir, "libbox").apply { mkdirs() }

            val options = SetupOptions().apply {
                basePath = baseDir.absolutePath
                workingPath = workingDir.absolutePath
                tempPath = tempDir.absolutePath
                fixAndroidStack = true
                commandServerListenPort = Libbox.availablePort(20000)
                commandServerSecret = UUID.randomUUID().toString()
                logMaxLines = 3000L
                debug = false
            }

            Libbox.setup(options)
            Libbox.setLocale(Locale.getDefault().toLanguageTag().replace('-', '_'))
            Libbox.redirectStderr(File(workingDir, "stderr.log").absolutePath)

            setupDone = true
            Log.d(TAG, "libbox setup complete: ${workingDir.absolutePath}")
        }
    }
}
