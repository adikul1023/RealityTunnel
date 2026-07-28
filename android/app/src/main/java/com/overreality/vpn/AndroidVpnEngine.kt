package com.overreality.vpn

import android.content.Context

interface AndroidVpnEngine {
    val name: String

    fun isAvailable(): Boolean

    fun unavailableReason(): String?

    /** Start the VPN core. The engine calls back [io.nekohasekai.libbox.PlatformInterface.openTun]
     *  on the context that was passed to [AndroidVpnEngineProvider.create] to create the TUN. */
    fun start(serverIp: String)

    fun stop()
}

object AndroidVpnEngineProvider {
    fun create(context: Context): AndroidVpnEngine = LibboxVpnEngine(context)
}
