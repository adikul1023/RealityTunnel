package com.overreality.vpn.models

enum class SessionState {
    AUTHENTICATED,
    REFRESHING,
    EXPIRED,
    REPLAY_DETECTED,
    OFFLINE
}
