package com.overreality.vpn.auth

import com.overreality.vpn.data.SecureStorage

import com.overreality.vpn.models.JwtTokens
import com.overreality.vpn.models.SessionState
import java.time.Instant

class TokenRepository(private val storage: SecureStorage) {

    private var currentTokens: JwtTokens? = storage.getJwtTokens()

    fun getCurrentTokens(): JwtTokens? {
        val mem = currentTokens
        if (mem == null || Instant.now().toEpochMilli() >= mem.expiresAt - 5000) {
            currentTokens = storage.getJwtTokens()
        }
        return currentTokens
    }

    fun getCurrentState(): SessionState {
        val tokens = currentTokens ?: return SessionState.OFFLINE
        
        if (Instant.now().toEpochMilli() >= tokens.expiresAt) {
            return SessionState.EXPIRED
        }
        
        return SessionState.AUTHENTICATED
    }

    fun updateTokens(tokens: JwtTokens) {
        currentTokens = tokens
        storage.saveJwtTokens(tokens)
    }

    fun updateTokensInMemoryOnly(tokens: JwtTokens) {
        currentTokens = tokens
    }

    fun clearTokens() {
        currentTokens = null
        storage.clearAll()
    }

    fun handleReplayDetected() {
        clearTokens()
    }
}
