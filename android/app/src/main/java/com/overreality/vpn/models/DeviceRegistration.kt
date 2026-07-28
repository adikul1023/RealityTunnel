package com.overreality.vpn.models

data class DeviceRegistration(
    val deviceGuid: String,
    val deviceName: String,
    val platform: String,
    val appVersion: String,
    val osVersion: String
)
