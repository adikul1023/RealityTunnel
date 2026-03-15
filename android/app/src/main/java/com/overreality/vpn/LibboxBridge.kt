package com.overreality.vpn

object LibboxBridge {
    private var loaded = false

    fun ensureLoaded() {
        if (loaded) return

        // Placeholder native bridge for future real libbox integration.
        // Expected native lib name at runtime: libbox_jni.so
        System.loadLibrary("box_jni")
        loaded = true
    }

    external fun start(configPath: String, tunFd: Int): String?
    external fun stop()
}
