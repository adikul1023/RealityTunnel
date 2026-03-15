package com.overreality.vpn

import android.content.Context
import io.nekohasekai.libbox.PlatformInterface

class LibboxVpnEngine(private val context: Context) : AndroidVpnEngine {
    private val manager = LibboxManager(context)

    override val name: String = "libbox"

    override fun isAvailable(): Boolean = manager.isAvailable()

    override fun unavailableReason(): String? {
        if (isAvailable()) return null
        return "libbox.aar not found. " +
            "Download it from https://github.com/SagerNet/sing-box-for-android/releases " +
            "and place it at android/app/libs/libbox.aar, then sync Gradle."
    }

    override fun start(serverIp: String) {
        // context is OverRealityVpnService which implements PlatformInterface.
        // libbox will call back platform.openTun() to create the TUN via VpnService.Builder.
        val platform = context as? PlatformInterface
            ?: throw IllegalStateException(
                "${context::class.simpleName} must implement PlatformInterface to use libbox")
        manager.start(serverIp, platform)
    }

    override fun stop() {
        manager.stop()
    }
}
