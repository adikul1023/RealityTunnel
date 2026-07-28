package com.overreality.vpn.models

@androidx.annotation.Keep
data class VpnProfileDto(
    val uuid: String,
    @com.google.gson.annotations.SerializedName("server_host") val server_ip: String,
    val server_port: Int,
    val public_key: String,
    val sni: String,
    @com.google.gson.annotations.SerializedName("preferred_dns") val dns: String? = null,
    val short_id: String? = null
)

@androidx.annotation.Keep
data class ClientMeResponse(
    val account_id: String,
    val status: String,
    val subscription_expires_at: String?,
    val device_count: Int,
    val plan: String,
    val email: String?,
    val two_factor_enabled: Boolean
)

@androidx.annotation.Keep
data class ClientUpdateResponse(
    val latest_version: String,
    val minimum_supported_version: String,
    val mandatory: Boolean,
    val download_url: String,
    val sha256: String,
    val release_notes: String
)

@androidx.annotation.Keep
data class DeviceStatusResponse(
    val active: Boolean,
    val reason: String?,
    val server_time: String
)

@androidx.annotation.Keep
data class ClientConfigResponse(
    @com.google.gson.annotations.SerializedName("vpn_profile") val vpnProfile: VpnProfileDto,
    @com.google.gson.annotations.SerializedName("license_blob") val licenseBlob: LicenseBlob
)
