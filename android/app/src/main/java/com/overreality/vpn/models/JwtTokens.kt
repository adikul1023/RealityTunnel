package com.overreality.vpn.models

@androidx.annotation.Keep
data class JwtTokens(
    val accessToken: String,
    val refreshToken: String,
    val expiresAt: Long // Epoch milliseconds
)
