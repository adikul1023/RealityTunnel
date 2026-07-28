package com.overreality.vpn

import com.overreality.vpn.auth.AuthenticationManager
import com.overreality.vpn.data.OracleApiClient
import com.overreality.vpn.logging.ClientLogger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class DeviceHeartbeatService(
    private val apiClient: OracleApiClient,
    private val authManager: AuthenticationManager,
    private val clientLogger: ClientLogger,
    private val onTerminateSession: () -> Unit
) {
    private var heartbeatJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO)

    fun startHeartbeat() {
        if (heartbeatJob?.isActive == true) return

        heartbeatJob = scope.launch {
            clientLogger.log(com.overreality.vpn.logging.LogLevel.INFO, "HEARTBEAT", "Starting device heartbeat loop")
            while (isActive) {
                try {
                    val token = authManager.getValidAccessToken()
                    if (token == null) {
                        clientLogger.log(com.overreality.vpn.logging.LogLevel.WARN, "HEARTBEAT", "No valid access token. Skipping heartbeat.")
                        delay(60_000L)
                        continue
                    }

                    val statusResponse = apiClient.fetchDeviceStatus(token)
                    if (statusResponse != null) {
                        if (!statusResponse.active) {
                            clientLogger.log(com.overreality.vpn.logging.LogLevel.WARN, "HEARTBEAT", "Device marked inactive (revoked). Terminating session.")
                            terminateSession()
                            break
                        }
                    } else {
                        // Transient error, ride it out
                        clientLogger.log(com.overreality.vpn.logging.LogLevel.WARN, "HEARTBEAT", "Transient heartbeat failure. Will retry.")
                    }
                } catch (e: SecurityException) {
                    if (e.message == "ReplayDetected") {
                        clientLogger.log(com.overreality.vpn.logging.LogLevel.WARN, "HEARTBEAT", "Fatal token error detected. Terminating session.")
                        terminateSession()
                        break
                    }
                } catch (e: Exception) {
                    clientLogger.log(com.overreality.vpn.logging.LogLevel.WARN, "HEARTBEAT", "Heartbeat error: ${e.message}")
                }
                
                // Ping every 30 seconds
                delay(30_000L)
            }
        }
    }

    fun stopHeartbeat() {
        clientLogger.log(com.overreality.vpn.logging.LogLevel.INFO, "HEARTBEAT", "Stopping device heartbeat loop")
        heartbeatJob?.cancel()
        heartbeatJob = null
    }

    private fun terminateSession() {
        authManager.logout()
        onTerminateSession()
    }
}
