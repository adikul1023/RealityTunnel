package com.overreality.vpn.models
import com.google.gson.annotations.SerializedName

sealed class LoginResult {
    data class Success(val tokens: JwtTokens) : LoginResult()
    data class DeviceLimitExceeded(val details: DeviceLimitDetails) : LoginResult()
    object ReplayDetected : LoginResult()
    data class Requires2FA(val temporaryLoginToken: String) : LoginResult()
    object SubscriptionExpired : LoginResult()
    object MandatoryUpdate : LoginResult()
    data class MaintenanceMode(val retryAfterSeconds: Int? = null) : LoginResult()
    object OfflineGraceExpired : LoginResult()
    data class Error(val message: String) : LoginResult()
}

sealed class ExchangeResult {
    data class Success(val tokens: JwtTokens, val isInitialProvisioning: Boolean) : ExchangeResult()
    data class Error(val message: String) : ExchangeResult()
}

data class DeviceLimitDetails(
    @SerializedName("current_devices") val currentDevices: Int,
    @SerializedName("max_devices") val maxDevices: Int,
    @SerializedName("manage_devices_url") val manageDevicesUrl: String
)

data class Verify2FaRequest(
    @SerializedName("temporary_login_token") val temporaryLoginToken: String,
    @SerializedName("totp_code") val totpCode: String
)

data class ApiErrorResponse(
    val error: String,
    @SerializedName("current_devices") val currentDevices: Int?,
    @SerializedName("max_devices") val maxDevices: Int?,
    @SerializedName("manage_devices_url") val manageDevicesUrl: String?,
    @SerializedName("temporary_login_token") val temporaryLoginToken: String?
)

data class ExchangeRequestDto(
    @SerializedName("exchange_token") val exchangeToken: String,
    @SerializedName("device_guid") val deviceGuid: String
)

data class ExchangeResponseDto(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("expires_in") val expiresIn: Long,
    @SerializedName("is_initial_provisioning") val isInitialProvisioning: Boolean
)
