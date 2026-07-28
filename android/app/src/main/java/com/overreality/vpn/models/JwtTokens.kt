package com.overreality.vpn.models

data class JwtTokens(
    val accessToken: String,
    val refreshToken: String,
    val expiresAt: Long // Epoch milliseconds
)
