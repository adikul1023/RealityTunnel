package com.overreality.vpn.auth

import com.overreality.vpn.data.SecureStorage

import com.overreality.vpn.models.LicenseBlob

class LicenseRepository(private val storage: SecureStorage) {

    private var currentBlob: LicenseBlob? = storage.getLicenseBlob()

    fun updateLicenseBlob(blob: LicenseBlob) {
        currentBlob = blob
        storage.saveLicenseBlob(blob)
    }

    fun isGracePeriodValid(): Boolean {
        val now = System.currentTimeMillis()
        val lastTrusted = storage.getLastTrustedTimestamp()
        
        // Clock rollback detected (allow 1 hour drift for NTP syncs)
        if (lastTrusted != null && now < lastTrusted - (60L * 60 * 1000)) {
            return false
        }
        
        // Hard maximum offline window (72 hours)
        if (lastTrusted != null && now > lastTrusted + (72L * 60 * 60 * 1000)) {
            return false
        }

        // Stub: Phase 8.3 will verify signature
        return true
    }

    fun verifySignatureOffline() {
        // Stub: Validate Ed25519 or ECDSA signature using hardcoded public key
    }
}
