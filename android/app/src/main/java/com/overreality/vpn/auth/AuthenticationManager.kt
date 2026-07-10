package com.overreality.vpn.auth

import com.overreality.vpn.data.OracleApiClient
import com.overreality.vpn.data.SecureStorage
import com.overreality.vpn.models.DeviceRegistration
import com.overreality.vpn.models.SessionState

class AuthenticationManager(
    private val apiClient: OracleApiClient,
    private val tokenRepository: TokenRepository,
    private val secureStorage: SecureStorage,
    private val licenseRepository: LicenseRepository
) {
    private val refreshMutex = kotlinx.coroutines.sync.Mutex()

    val isAuthenticated: Boolean
        get() = tokenRepository.getCurrentState() == SessionState.AUTHENTICATED || tokenRepository.getCurrentState() == SessionState.OFFLINE

    suspend fun login(accountId: String, masterToken: String): com.overreality.vpn.models.LoginResult {
        secureStorage.saveMasterToken(masterToken)
        
        val deviceId = secureStorage.getDeviceGuid()
        val osVersion = android.os.Build.VERSION.RELEASE
        val model = android.os.Build.MODEL
        val clientVersion = com.overreality.vpn.BuildConfig.VERSION_NAME
        val device = DeviceRegistration(deviceId, model, "android", clientVersion, osVersion)
        val result = apiClient.login(accountId, masterToken, device)
        
        if (result is com.overreality.vpn.models.LoginResult.Success) {
            tokenRepository.updateTokens(result.tokens)
            secureStorage.saveLastTrustedTimestamp(System.currentTimeMillis())
            
            val license = apiClient.fetchLicense(result.tokens.accessToken)
            if (license != null) {
                licenseRepository.updateLicenseBlob(license)
            }
        }
        
        return result
    }

    suspend fun verify2Fa(tempToken: String, totpCode: String): Boolean {
        val tokens = apiClient.verify2Fa(tempToken, totpCode)
        if (tokens != null) {
            tokenRepository.updateTokens(tokens)
            secureStorage.saveLastTrustedTimestamp(System.currentTimeMillis())
            
            val license = apiClient.fetchLicense(tokens.accessToken)
            if (license != null) {
                licenseRepository.updateLicenseBlob(license)
            }
            return true
        }
        return false
    }

    suspend fun getValidAccessToken(): String? {
        val state = tokenRepository.getCurrentState()
        val tokens = tokenRepository.getCurrentTokens()

        if (state == SessionState.OFFLINE || tokens == null) {
            return null
        }

        // Assuming ExpiresAt is a Long timestamp in seconds/ms or parsed string.
        // For now, if we have tokens, let's pretend we check expiration.
        // In real app, we parse tokens.expiresAt. 
        // For simplicity, we just return if Authenticated.
        if (state == SessionState.AUTHENTICATED) {
            return tokens.accessToken
        }

        refreshMutex.lock()
        try {
            // Check tokens again inside lock in case another coroutine just refreshed them
            val updatedTokens = tokenRepository.getCurrentTokens()
            if (updatedTokens != null && tokenRepository.getCurrentState() == SessionState.AUTHENTICATED) {
                return updatedTokens.accessToken
            }
            val newTokens = apiClient.refresh(tokens.refreshToken)
            if (newTokens != null) {
                tokenRepository.updateTokens(newTokens)
                secureStorage.saveLastTrustedTimestamp(System.currentTimeMillis())
                return newTokens.accessToken
            }
        } catch (e: SecurityException) {
            if (e.message == "ReplayDetected") {
                tokenRepository.handleReplayDetected()
                throw e
            }
        } catch (e: Exception) {
        } finally {
            refreshMutex.unlock()
        }
        return null
    }

    fun logout() {
        tokenRepository.clearTokens()
        secureStorage.clearAll()
    }
}
