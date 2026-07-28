package com.overreality.vpn.models

@androidx.annotation.Keep
data class AccountInfo(
    val accountId: String,
    val twoFactorEnabled: Boolean
)
