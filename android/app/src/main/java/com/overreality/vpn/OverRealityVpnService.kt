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
import android.util.Log
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

    private fun updateForegroundNotification(message: String, connected: Boolean) {
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
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            try {
                startForeground(
                    NOTIFICATION_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
                )
            } catch (t: Throwable) {
                Log.w(TAG, "specialUse foreground failed, falling back", t)
                startForeground(NOTIFICATION_ID, notification)
            }
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    @Throws(Exception::class)
    override fun openTun(options: TunOptions): Int {
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

        val dnsRaw = options.getDNSServerAddress().value
        val dnsItems = dnsRaw
            .split(',', ' ', ';', '|')
            .map { it.trim() }
            .filter { it.isNotBlank() }
        var addedDns = false
        for (dns in dnsItems) {
            builder.addDnsServer(dns)
            addedDns = true
        }

        // If libbox provides only internal DNS (10.0.85.3) or none, fall back to current
        // network DNS servers so Chrome/system resolver don't time out with BAD_CONFIG.
        if (!addedDns || (dnsItems.size == 1 && dnsItems[0] == "10.0.85.3")) {
            val cm = getSystemService(ConnectivityManager::class.java)
            val active = cm?.activeNetwork
            val systemDns = if (active != null) {
                cm.getLinkProperties(active)
                    ?.dnsServers
                    ?.mapNotNull { it.hostAddress }
                    ?.filter { it.isNotBlank() && !it.contains(':') }
                    .orEmpty()
            } else {
                emptyList()
            }
            val fallbackDns = if (systemDns.isNotEmpty()) systemDns else listOf("8.8.8.8", "4.2.2.2")
            for (dns in fallbackDns) {
                builder.addDnsServer(dns)
            }
            Log.d(TAG, "openTun: using fallback DNS $fallbackDns")
        } else {
            Log.d(TAG, "openTun: using libbox DNS $dnsItems")
        }

        try {
            builder.addDisallowedApplication(packageName)
        } catch (_: PackageManager.NameNotFoundException) {
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            builder.setMetered(false)
        }

        val pfd = builder.establish() ?: throw Exception("VpnService.Builder.establish() returned null")
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
                ctx.rawSuccess(ByteArray(0))
            }

            override fun lookup(ctx: ExchangeContext, network: String, domain: String) {
                ctx.success("")
            }

            override fun raw(): Boolean {
                return true
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        engine = AndroidVpnEngineProvider.create(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        try {
            when (intent?.action) {
                ACTION_START -> {
                    ensureForeground()
                    val serverIp = intent.getStringExtra(EXTRA_SERVER_IP).orEmpty()
                    startVpn(serverIp)
                }

                ACTION_STOP -> stopVpn()
            }
        } catch (t: Throwable) {
            stopVpn()
            VpnStatusStore.setState(
                VpnConnectionState.ERROR,
                "[${engine.name}] startup failed: ${t.message ?: t::class.java.simpleName}",
            )
            Log.e(TAG, "onStartCommand failed", t)
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onRevoke() {
        stopVpn()
        super.onRevoke()
    }

    override fun onDestroy() {
        stopVpn()
        super.onDestroy()
    }

    private fun startVpn(serverIp: String) {
        if (tunPfd != null) {
            VpnStatusStore.setState(VpnConnectionState.CONNECTED, "Already connected")
            updateForegroundNotification("Connected", connected = true)
            return
        }

        VpnStatusStore.setState(VpnConnectionState.CONNECTING, "Preparing tunnel")
        updateForegroundNotification("Connecting", connected = false)

        try {
            if (!engine.isAvailable()) {
                throw IllegalStateException(engine.unavailableReason() ?: "VPN engine unavailable")
            }
            engine.start(serverIp)
            val msg = if (serverIp.isBlank()) "Connected (${engine.name})"
            else "Connected (${engine.name}): $serverIp"
            VpnStatusStore.setState(VpnConnectionState.CONNECTED, msg)
            updateForegroundNotification("Connected", connected = true)
        } catch (t: Throwable) {
            stopVpn()
            VpnStatusStore.setState(
                VpnConnectionState.ERROR,
                "[${engine.name}] ${t.message ?: t::class.java.simpleName}",
            )
        }
    }

    private fun stopVpn() {
        try {
            engine.stop()
        } catch (_: Exception) {
        }
        try {
            tunPfd?.close()
        } catch (_: Exception) {
        } finally {
            tunPfd = null
        }
        stopForeground(STOP_FOREGROUND_REMOVE)
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
