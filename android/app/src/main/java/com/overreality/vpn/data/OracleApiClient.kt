package com.overreality.vpn.data

import com.google.gson.Gson
import com.overreality.vpn.BuildConfig
import com.overreality.vpn.models.ClientMeResponse
import com.overreality.vpn.models.ClientUpdateResponse
import com.overreality.vpn.models.DeviceRegistration
import com.overreality.vpn.models.JwtTokens
import com.overreality.vpn.models.LicenseBlob
import com.overreality.vpn.models.VpnProfileDto
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.CertificatePinner
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response

class OracleApiClient {
    private val client = OkHttpClient.Builder()
        .addInterceptor(ResilientInterceptor())
        .addInterceptor { chain ->
            val request = chain.request().newBuilder()
                .header("User-Agent", "Stealthy-Android/1.0.0-beta")
                .build()
            chain.proceed(request)
        }
        // Set to true once the real SPKI pin is available
        .apply {
            val enablePinning = false
            if (enablePinning) {
                // To enable pinning, add the actual pin like:
                // certificatePinner(
                //     okhttp3.CertificatePinner.Builder()
                //         .add("api.stealthy.co.in", "sha256/ACTUAL_PIN_HERE")
                //         .build()
                // )
            }
        }
        .build()
        
    private val gson = Gson()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun login(accountId: String, masterToken: String, device: DeviceRegistration): com.overreality.vpn.models.LoginResult = withContext(Dispatchers.IO) {
        val json = """
            {
                "account_id": "$accountId",
                "master_token": "$masterToken",
                "device_guid": "${device.deviceGuid}",
                "client_type": "android"
            }
        """.trimIndent()
        
        val request = Request.Builder()
            .url("${BuildConfig.API_BASE_URL}/api/auth/login")
            .post(json.toRequestBody(jsonMediaType))
            .build()
            
        client.newCall(request).execute().use { response ->
            if (response.isSuccessful) {
                val tokens = gson.fromJson(response.body?.string(), JwtTokens::class.java)
                return@withContext com.overreality.vpn.models.LoginResult.Success(tokens)
            }
            
            if (response.code == 403) {
                val bodyStr = response.body?.string() ?: ""
                if (bodyStr.contains("DEVICE_LIMIT_EXCEEDED")) {
                    val errorBody = try { gson.fromJson(bodyStr, com.overreality.vpn.models.ApiErrorResponse::class.java) } catch (e: Exception) { null }
                    val details = com.overreality.vpn.models.DeviceLimitDetails(
                        currentDevices = errorBody?.currentDevices ?: 0,
                        maxDevices = errorBody?.maxDevices ?: 0,
                        manageDevicesUrl = errorBody?.manageDevicesUrl.orEmpty()
                    )
                    return@withContext com.overreality.vpn.models.LoginResult.DeviceLimitExceeded(details)
                }
                if (bodyStr.contains("DEVICE_OWNERSHIP_ERROR")) {
                    return@withContext com.overreality.vpn.models.LoginResult.Error("This device is already registered to another account.")
                }
                if (bodyStr.contains("DEVICE_DEACTIVATED") || bodyStr.contains("Device is deactivated")) {
                    return@withContext com.overreality.vpn.models.LoginResult.Error("This device has been deactivated.")
                }
                return@withContext com.overreality.vpn.models.LoginResult.Error("Access Denied (403).")
            }
            
            if (response.code == 401) {
                val errorBody = gson.fromJson(response.body?.string(), com.overreality.vpn.models.ApiErrorResponse::class.java)
                if (errorBody?.error == "requires_2fa" && errorBody.temporaryLoginToken != null) {
                    return@withContext com.overreality.vpn.models.LoginResult.Requires2FA(errorBody.temporaryLoginToken)
                }
            }
            
            if (response.code == 400 || response.code == 409) {
                val bodyStr = response.body?.string() ?: ""
                if (bodyStr.contains("DEVICE_LIMIT_EXCEEDED") || bodyStr.contains("device_limit_exceeded")) {
                    val errorBody = try { gson.fromJson(bodyStr, com.overreality.vpn.models.ApiErrorResponse::class.java) } catch (e: Exception) { null }
                    val details = com.overreality.vpn.models.DeviceLimitDetails(
                        currentDevices = errorBody?.currentDevices ?: 0,
                        maxDevices = errorBody?.maxDevices ?: 0,
                        manageDevicesUrl = errorBody?.manageDevicesUrl.orEmpty()
                    )
                    return@withContext com.overreality.vpn.models.LoginResult.DeviceLimitExceeded(details)
                }
            }
            
            return@withContext com.overreality.vpn.models.LoginResult.Error(response.message)
        }
    }

    suspend fun verify2Fa(tempToken: String, totpCode: String): JwtTokens? = withContext(Dispatchers.IO) {
        val json = gson.toJson(com.overreality.vpn.models.Verify2FaRequest(tempToken, totpCode))
        val request = Request.Builder()
            .url("${BuildConfig.API_BASE_URL}/api/auth/verify-2fa")
            .post(json.toRequestBody(jsonMediaType))
            .build()
            
        client.newCall(request).execute().use { response ->
            if (response.isSuccessful) {
                return@withContext gson.fromJson(response.body?.string(), JwtTokens::class.java)
            }
        }
        return@withContext null
    }

    suspend fun exchangeToken(exchangeToken: String, deviceGuid: String): com.overreality.vpn.models.ExchangeResult = withContext(Dispatchers.IO) {
        val dto = com.overreality.vpn.models.ExchangeRequestDto(exchangeToken, deviceGuid)
        val json = gson.toJson(dto)
        val request = Request.Builder()
            .url("${BuildConfig.API_BASE_URL}/api/auth/exchange")
            .post(json.toRequestBody(jsonMediaType))
            .build()

        client.newCall(request).execute().use { response ->
            if (response.isSuccessful && response.body != null) {
                val bodyStr = response.body?.string()
                val respDto = gson.fromJson(bodyStr, com.overreality.vpn.models.ExchangeResponseDto::class.java)
                if (respDto != null) {
                    val tokens = JwtTokens(respDto.accessToken, respDto.refreshToken, System.currentTimeMillis() + respDto.expiresIn * 1000L)
                    return@withContext com.overreality.vpn.models.ExchangeResult.Success(tokens, respDto.isInitialProvisioning)
                }
            }
            return@withContext com.overreality.vpn.models.ExchangeResult.Error(response.message)
        }
    }

    suspend fun refresh(refreshToken: String): JwtTokens? = withContext(Dispatchers.IO) {
        val json = """{"refresh_token": "$refreshToken"}"""
        
        val request = Request.Builder()
            .url("${BuildConfig.API_BASE_URL}/api/auth/refresh")
            .post(json.toRequestBody(jsonMediaType))
            .build()
            
        client.newCall(request).execute().use { response ->
            if (response.isSuccessful) {
                return@withContext gson.fromJson(response.body?.string(), JwtTokens::class.java)
            }
            if (response.code == 401 || response.code == 403) {
                val bodyStr = response.body?.string()
                val errorBody = try { gson.fromJson(bodyStr, com.overreality.vpn.models.ApiErrorResponse::class.java) } catch (e: Exception) { null }
                if (response.code == 403 || errorBody?.error == "DEVICE_REVOKED" || errorBody?.error == "REPLAY_DETECTED" || errorBody?.error == "INVALID_TOKEN") {
                    throw SecurityException("ReplayDetected")
                }
            }
        }
        return@withContext null
    }

    suspend fun fetchClientConfig(accessToken: String): com.overreality.vpn.models.ClientConfigResponse? = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("${BuildConfig.API_BASE_URL}/api/client/config")
            .header("Authorization", "Bearer $accessToken")
            .build()
            
        client.newCall(request).execute().use { response ->
            if (response.isSuccessful) {
                return@withContext gson.fromJson(response.body?.string(), com.overreality.vpn.models.ClientConfigResponse::class.java)
            }
        }
        return@withContext null
    }


    suspend fun fetchClientMe(accessToken: String): ClientMeResponse? = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("${BuildConfig.API_BASE_URL}/api/client/me")
            .header("Authorization", "Bearer $accessToken")
            .build()
            
        client.newCall(request).execute().use { response ->
            if (response.isSuccessful) {
                return@withContext gson.fromJson(response.body?.string(), ClientMeResponse::class.java)
            }
        }
        return@withContext null
    }

    suspend fun fetchDeviceStatus(accessToken: String): com.overreality.vpn.models.DeviceStatusResponse? = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("${BuildConfig.API_BASE_URL}/api/devices/status")
            .header("Authorization", "Bearer $accessToken")
            .build()
            
        client.newCall(request).execute().use { response ->
            if (response.isSuccessful) {
                return@withContext gson.fromJson(response.body?.string(), com.overreality.vpn.models.DeviceStatusResponse::class.java)
            }
            if (response.code == 401 || response.code == 403) {
                val bodyStr = response.body?.string()
                val errorBody = try { gson.fromJson(bodyStr, com.overreality.vpn.models.ApiErrorResponse::class.java) } catch (e: Exception) { null }
                if (response.code == 403 || errorBody?.error == "DEVICE_REVOKED" || errorBody?.error == "REPLAY_DETECTED" || errorBody?.error == "INVALID_TOKEN") {
                    throw SecurityException("ReplayDetected")
                }
            }
        }
        return@withContext null
    }

    suspend fun fetchClientUpdate(): ClientUpdateResponse? = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("${BuildConfig.API_BASE_URL}/api/client/update")
            .build()
            
        client.newCall(request).execute().use { response ->
            if (response.isSuccessful) {
                return@withContext gson.fromJson(response.body?.string(), ClientUpdateResponse::class.java)
            }
        }
        return@withContext null
    }
}
