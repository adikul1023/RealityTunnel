package com.overreality.vpn.data

import android.content.Context
import android.content.SharedPreferences
import com.overreality.vpn.auth.LicenseRepository
import com.overreality.vpn.auth.AuthenticationManager
import kotlinx.coroutines.launch

class ConfigurationProvider(
    private val context: Context,
    private val licenseRepository: LicenseRepository,
    private val secureStorage: SecureStorage,
    private val authManager: AuthenticationManager,
    private val apiClient: OracleApiClient
) {
    private val prefs: SharedPreferences = context.getSharedPreferences("vpn_prefs", Context.MODE_PRIVATE)

    suspend fun getVpnProfile(): com.overreality.vpn.models.VpnProfileDto? {
        val cachedProfile = secureStorage.getVpnProfile()
        if (cachedProfile != null && licenseRepository.isGracePeriodValid()) {
            kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
                refreshProfileFromNetwork()
            }
            return cachedProfile
        }
        
        return refreshProfileFromNetwork()
    }

    suspend fun refreshProfileBackground() {
        refreshProfileFromNetwork()
    }

    suspend fun fetchVpnProfile(): com.overreality.vpn.models.VpnProfileDto? {
        return refreshProfileFromNetwork()
    }

    private suspend fun refreshProfileFromNetwork(): com.overreality.vpn.models.VpnProfileDto? {
        val token = authManager.getValidAccessToken() ?: return getDebugProfile()
        try {
            val remoteConfig = apiClient.fetchClientConfig(token)
            if (remoteConfig != null) {
                secureStorage.saveVpnProfile(remoteConfig.vpnProfile)
                licenseRepository.updateLicenseBlob(remoteConfig.licenseBlob)
                return remoteConfig.vpnProfile
            }
        } catch (e: Exception) {
            // Fallback to cache on network failure
        }
        return getDebugProfile()
    }

    private fun getDebugProfile(): com.overreality.vpn.models.VpnProfileDto? {
        if (com.overreality.vpn.BuildConfig.DEBUG) {
            val serverIp = prefs.getString("server_ip", "")
            if (!serverIp.isNullOrEmpty()) {
                return com.overreality.vpn.models.VpnProfileDto(
                    server_ip = serverIp,
                    uuid = "00000000-0000-0000-0000-000000000000",
                    public_key = "dummy-key",
                    sni = "www.microsoft.com"
                )
            }
        }
        return null
    }
}
