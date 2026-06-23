package com.overreality.vpn

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.net.ConnectivityManager
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import android.os.Process
import android.util.Log
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import androidx.core.app.NotificationCompat
import io.nekohasekai.libbox.ConnectionOwner
import io.nekohasekai.libbox.ExchangeContext
import io.nekohasekai.libbox.InterfaceUpdateListener
import io.nekohasekai.libbox.LocalDNSTransport
import io.nekohasekai.libbox.NetworkInterface
import io.nekohasekai.libbox.NetworkInterfaceIterator
import io.nekohasekai.libbox.Notification
import io.nekohasekai.libbox.PlatformInterface
import io.nekohasekai.libbox.StringIterator
import io.nekohasekai.libbox.TunOptions
import io.nekohasekai.libbox.WIFIState

class OverRealityVpnService : VpnService(), PlatformInterface {
    private var tunPfd: ParcelFileDescriptor? = null
    private lateinit var engine: AndroidVpnEngine

    private fun logWithMetadata(message: String) {
        val timestamp = SimpleDateFormat("HH:mm:ss.SSS", Locale.US).format(Date())
        val pid = Process.myPid()
        val tid = Process.myTid()
        val thread = Thread.currentThread().name
        Log.d(TAG, "[$timestamp] PID:$pid TID:$tid Thread:$thread - $message")
    }

    private fun updateForegroundNotification(message: String, connected: Boolean) {
        logWithMetadata("updateForegroundNotification: message='$message', connected=$connected")
        val nm = getSystemService(NotificationManager::class.java)
        val openIntent = Intent(this, MainActivity::class.java)
        val openPendingIntent = PendingIntent.getActivity(
            this,
            1,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val stopIntent = Intent(this, OverRealityVpnService::class.java)
            .setAction(ACTION_STOP)
        val stopPendingIntent = PendingIntent.getService(
            this,
            2,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notification = NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification_vpn)
            .setContentTitle("OverREALITY")
            .setContentText(message)
            .setContentIntent(openPendingIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .addAction(0, "Disconnect", stopPendingIntent)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()

        if (connected) {
            nm.notify(NOTIFICATION_ID, notification)
            logWithMetadata("updateForegroundNotification: notification updated (connected state)")
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            try {
                startForeground(
                    NOTIFICATION_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
                )
                logWithMetadata("updateForegroundNotification: startForeground called with SPECIAL_USE type")
            } catch (t: Throwable) {
                Log.w(TAG, "specialUse foreground failed, falling back", t)
                logWithMetadata("updateForegroundNotification: specialUse failed, falling back to standard foreground")
                startForeground(NOTIFICATION_ID, notification)
            }
        } else {
            startForeground(NOTIFICATION_ID, notification)
            logWithMetadata("updateForegroundNotification: startForeground called (standard)")
        }
    }

    @Throws(Exception::class)
    override fun openTun(options: TunOptions): Int {
        logWithMetadata("openTun: called with MTU=${options.getMTU()}")
        val builder = Builder()
            .setSession("OverREALITY")
            .setMtu(options.getMTU())

        val addr4 = options.getInet4Address()
        while (addr4.hasNext()) {
            val cidr = addr4.next().toString()
            val slash = cidr.lastIndexOf('/')
            builder.addAddress(cidr.substring(0, slash), cidr.substring(slash + 1).toInt())
        }

        // Add IPv4 routes from libbox. With inet4_route_address set in tun config, libbox
        // will provide "0.0.0.0/1" and "128.0.0.0/1". Fall back to those same split-default
        // routes if libbox provides none, to ensure all IPv4 traffic enters the tun.
        var ipv4RouteAdded = false
        val route4 = options.getInet4RouteAddress()
        while (route4.hasNext()) {
            val cidr = route4.next().toString()
            val slash = cidr.lastIndexOf('/')
            if (slash >= 0) {
                builder.addRoute(cidr.substring(0, slash), cidr.substring(slash + 1).toInt())
                ipv4RouteAdded = true
                Log.d(TAG, "openTun: route $cidr")
            }
        }
        if (!ipv4RouteAdded) {
            Log.w(TAG, "openTun: no IPv4 routes from libbox, adding split-default fallback")
            builder.addRoute("0.0.0.0", 1)
            builder.addRoute("128.0.0.0", 1)
        }

        // Use real DNS servers instead of libbox's fake TUN address (10.0.85.3).
        // The sing-box route rule "port: [53] -> direct" routes all DNS packets
        // via VpnService.protect() directly to the real network, completely bypassing
        // the proxy. This avoids all xUDP/EOF issues with the xray server for DNS.
        // Web traffic (non-port-53) still goes through the VLESS proxy as normal.
        val dnsRaw = options.getDNSServerAddress().value
        Log.d(TAG, "openTun: libbox DNS raw: '$dnsRaw' (ignored — using real DNS servers)")
        builder.addDnsServer("8.8.8.8")
        builder.addDnsServer("9.9.9.9")
        Log.d(TAG, "openTun: added real DNS 8.8.8.8 and 9.9.9.9 (routed via direct, not proxy)")

        try {
            builder.addDisallowedApplication(packageName)
        } catch (_: PackageManager.NameNotFoundException) {
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            builder.setMetered(false)
        }

        val pfd = builder.establish() ?: throw Exception("VpnService.Builder.establish() returned null")
        logWithMetadata("openTun: VPN file descriptor created successfully, fd=${pfd.fd}")
        tunPfd?.close()
        tunPfd = pfd
        return pfd.fd
    }

    @Throws(Exception::class)
    override fun usePlatformAutoDetectInterfaceControl(): Boolean = true

    @Throws(Exception::class)
    override fun autoDetectInterfaceControl(fd: Int) {
        if (!protect(fd)) {
            throw Exception("protect($fd) failed")
        }
    }

    @Throws(Exception::class)
    override fun findConnectionOwner(
        ipProtocol: Int,
        sourceAddress: String,
        sourcePort: Int,
        destinationAddress: String,
        destinationPort: Int,
    ): ConnectionOwner {
        val owner = ConnectionOwner()
        owner.userId = -1
        owner.userName = ""
        owner.processPath = ""
        owner.androidPackageName = ""
        return owner
    }

    @Throws(Exception::class)
    override fun readWIFIState(): WIFIState = WIFIState("", "")

    @Throws(Exception::class)
    override fun startDefaultInterfaceMonitor(listener: InterfaceUpdateListener) {
    }

    @Throws(Exception::class)
    override fun closeDefaultInterfaceMonitor(listener: InterfaceUpdateListener) {
    }

    @Throws(Exception::class)
    override fun underNetworkExtension(): Boolean = false

    @Throws(Exception::class)
    override fun includeAllNetworks(): Boolean = false

    @Throws(Exception::class)
    override fun clearDNSCache() {
    }

    @Throws(Exception::class)
    override fun useProcFS(): Boolean = Build.VERSION.SDK_INT < Build.VERSION_CODES.Q

    @Throws(Exception::class)
    override fun getInterfaces(): NetworkInterfaceIterator {
        return object : NetworkInterfaceIterator {
            override fun hasNext(): Boolean = false
            override fun next(): NetworkInterface {
                throw NoSuchElementException("No interface snapshot implementation")
            }
        }
    }

    @Throws(Exception::class)
    override fun sendNotification(notification: Notification) {
    }

    @Throws(Exception::class)
    override fun systemCertificates(): StringIterator {
        return object : StringIterator {
            override fun len(): Int = 0
            override fun hasNext(): Boolean = false
            override fun next(): String = ""
        }
    }

    @Throws(Exception::class)
    override fun localDNSTransport(): LocalDNSTransport {
        return object : LocalDNSTransport {
            override fun exchange(ctx: ExchangeContext, raw: ByteArray) {
                Log.d("LOCALDNS", "exchange called size=${raw.size}")
                ctx.rawSuccess(ByteArray(0))
            }

            override fun lookup(ctx: ExchangeContext, network: String, domain: String) {
                Log.d("LOCALDNS", "lookup called network=$network domain=$domain")
                ctx.success("")
            }

            override fun raw(): Boolean {
                return true
            }
        }
    }

    override fun onCreate() {
        logWithMetadata("onCreate: service created")
        super.onCreate()
        engine = AndroidVpnEngineProvider.create(this)
        logWithMetadata("onCreate: engine created: ${engine::class.simpleName}")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        logWithMetadata("onStartCommand: action=${intent?.action}, flags=$flags, startId=$startId")
        try {
            when (intent?.action) {
                ACTION_START -> {
                    logWithMetadata("onStartCommand: ACTION_START received")
                    ensureForeground()
                    val serverIp = intent.getStringExtra(EXTRA_SERVER_IP).orEmpty()
                    logWithMetadata("onStartCommand: starting VPN with serverIp='$serverIp'")
                    startVpn(serverIp)
                }

                ACTION_STOP -> {
                    logWithMetadata("onStartCommand: ACTION_STOP received")
                    stopVpn()
                }
                else -> {
                    logWithMetadata("onStartCommand: unknown action ${intent?.action}")
                }
            }
        } catch (t: Throwable) {
            logWithMetadata("onStartCommand: EXCEPTION - ${t.message}")
            Log.e(TAG, "onStartCommand failed", t)
            stopVpn()
            VpnStatusStore.setState(
                VpnConnectionState.ERROR,
                "[${engine.name}] startup failed: ${t.message ?: t::class.java.simpleName}",
            )
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onRevoke() {
        logWithMetadata("onRevoke: VPN revoked by system")
        stopVpn()
        super.onRevoke()
    }

    override fun onDestroy() {
        logWithMetadata("onDestroy: service destroying")
        stopVpn()
        super.onDestroy()
    }

    private fun startVpn(serverIp: String) {
        logWithMetadata("startVpn: called with serverIp='$serverIp'")
        if (tunPfd != null) {
            logWithMetadata("startVpn: already connected, tunPfd exists")
            VpnStatusStore.setState(VpnConnectionState.CONNECTED, "Already connected")
            updateForegroundNotification("Connected", connected = true)
            return
        }

        VpnStatusStore.setState(VpnConnectionState.CONNECTING, "Preparing tunnel")
        updateForegroundNotification("Connecting", connected = false)

        try {
            if (!engine.isAvailable()) {
                logWithMetadata("startVpn: engine not available - ${engine.unavailableReason()}")
                throw IllegalStateException(engine.unavailableReason() ?: "VPN engine unavailable")
            }
            logWithMetadata("startVpn: calling engine.start()")
            engine.start(serverIp)
            logWithMetadata("startVpn: engine.start() completed successfully")
            val msg = if (serverIp.isBlank()) "Connected (${engine.name})"
            else "Connected (${engine.name}): $serverIp"
            VpnStatusStore.setState(VpnConnectionState.CONNECTED, msg)
            updateForegroundNotification("Connected", connected = true)
        } catch (t: Throwable) {
            logWithMetadata("startVpn: EXCEPTION - ${t.message}")
            Log.e(TAG, "startVpn failed", t)
            stopVpn()
            VpnStatusStore.setState(
                VpnConnectionState.ERROR,
                "[${engine.name}] ${t.message ?: t::class.java.simpleName}",
            )
        }
    }

    private fun stopVpn() {
        logWithMetadata("stopVpn: called")
        try {
            logWithMetadata("stopVpn: calling engine.stop()")
            engine.stop()
            logWithMetadata("stopVpn: engine.stop() completed")
        } catch (t: Exception) {
            logWithMetadata("stopVpn: EXCEPTION in engine.stop() - ${t.message}")
            Log.e(TAG, "stopVpn: engine.stop() failed", t)
        }
        try {
            tunPfd?.close()
            logWithMetadata("stopVpn: tunPfd closed")
        } catch (t: Exception) {
            logWithMetadata("stopVpn: EXCEPTION closing tunPfd - ${t.message}")
            Log.e(TAG, "stopVpn: tunPfd.close() failed", t)
        } finally {
            tunPfd = null
        }
        stopForeground(STOP_FOREGROUND_REMOVE)
        logWithMetadata("stopVpn: foreground stopped")
        VpnStatusStore.setState(VpnConnectionState.DISCONNECTED)
        stopSelf()
    }

    private fun ensureForeground() {
        val channelId = NOTIFICATION_CHANNEL_ID
        val nm = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val existing = nm.getNotificationChannel(channelId)
            if (existing == null) {
                val channel = NotificationChannel(
                    channelId,
                    "OverREALITY VPN",
                    NotificationManager.IMPORTANCE_DEFAULT,
                )
                nm.createNotificationChannel(channel)
            }
        }
        updateForegroundNotification("Connecting", connected = false)
    }

    companion object {
        const val ACTION_START = "com.overreality.vpn.action.START"
        const val ACTION_STOP = "com.overreality.vpn.action.STOP"
        const val EXTRA_SERVER_IP = "extra_server_ip"
        private const val NOTIFICATION_CHANNEL_ID = "overreality_vpn_channel"
        private const val NOTIFICATION_ID = 1001
        private const val TAG = "OverRealityVpn"
    }
}
