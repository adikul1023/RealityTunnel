package com.overreality.vpn

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class VpnConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    ERROR,
}

data class VpnUiState(
    val state: VpnConnectionState = VpnConnectionState.DISCONNECTED,
    val message: String = "",
)

object VpnStatusStore {
    private val _state = MutableStateFlow(VpnUiState())
    val state: StateFlow<VpnUiState> = _state.asStateFlow()

    fun setState(newState: VpnConnectionState, message: String = "") {
        _state.value = VpnUiState(state = newState, message = message)
    }
}
