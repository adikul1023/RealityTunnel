package com.overreality.vpn

import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import com.overreality.vpn.data.ConfigurationProvider

class SessionManager(
    private val context: Context,
    private val configProvider: ConfigurationProvider
) {
    suspend fun startSession(serverIp: String? = null) {
        val ip = serverIp ?: configProvider.getVpnProfile()?.server_ip ?: ""
        if (ip.isNotEmpty()) {
            val intent = Intent(context, OverRealityVpnService::class.java)
                .setAction(OverRealityVpnService.ACTION_START)
                .putExtra(OverRealityVpnService.EXTRA_SERVER_IP, ip)
            ContextCompat.startForegroundService(context, intent)
        }
    }

    fun stopSession() {
        val intent = Intent(context, OverRealityVpnService::class.java)
            .setAction(OverRealityVpnService.ACTION_STOP)
        context.startService(intent)
    }
}
