package com.overreality.vpn.models

@androidx.annotation.Keep
data class LicenseBlob(
    val payload: String,
    val signature: String
)
