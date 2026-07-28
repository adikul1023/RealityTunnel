package com.overreality.vpn.models

data class VpnProfileDto(
    val uuid: String,
    val server_ip: String,
    val public_key: String,
    val sni: String,
    val dns: String? = null,
    val short_id: String? = null
)

data class ClientMeResponse(
    val account_id: String,
    val status: String,
    val subscription_expires_at: String?,
    val device_count: Int,
    val plan: String,
    val email: String?,
    val two_factor_enabled: Boolean
)

data class ClientUpdateResponse(
    val latest_version: String,
    val minimum_supported_version: String,
    val mandatory: Boolean,
    val download_url: String,
    val sha256: String,
    val release_notes: String
)

data class DeviceStatusResponse(
    val active: Boolean,
    val reason: String?,
    val server_time: String
)

data class ClientConfigResponse(
    @com.google.gson.annotations.SerializedName("vpn_profile") val vpnProfile: VpnProfileDto,
    @com.google.gson.annotations.SerializedName("license_blob") val licenseBlob: LicenseBlob
)
