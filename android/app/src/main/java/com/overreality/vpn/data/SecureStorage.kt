package com.overreality.vpn.data

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.google.gson.Gson
import com.overreality.vpn.models.JwtTokens
import com.overreality.vpn.models.LicenseBlob
import com.overreality.vpn.models.VpnProfileDto

class SecureStorage(context: Context) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val sharedPrefs = try {
        EncryptedSharedPreferences.create(
            context,
            "stealthy_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    } catch (e: Exception) {
        try { context.deleteSharedPreferences("stealthy_secure_prefs") } catch (ignored: Exception) {}
        EncryptedSharedPreferences.create(
            context,
            "stealthy_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    fun saveMasterToken(token: String) {
        val bytes = token.toByteArray(Charsets.UTF_8)
        try {
            sharedPrefs.edit().putString("master_token", token).commit()
        } finally {
            bytes.fill(0.toByte())
        }
    }

    fun getMasterToken(): CharArray? {
        val token = sharedPrefs.getString("master_token", null) ?: return null
        val chars = token.toCharArray()
        // Returning CharArray so the caller can zero it out
        return chars
    }

    private val gson = Gson()

    fun saveJwtTokens(tokens: JwtTokens) {
        sharedPrefs.edit().putString("jwt_tokens", gson.toJson(tokens)).commit()
    }

    fun getJwtTokens(): JwtTokens? {
        val json = sharedPrefs.getString("jwt_tokens", null) ?: return null
        return try {
            gson.fromJson(json, JwtTokens::class.java)
        } catch (e: Exception) {
            sharedPrefs.edit()
                .putString("jwt_tokens.corrupt", json)
                .remove("jwt_tokens")
                .apply()
            null
        }
    }

    fun saveLicenseBlob(blob: LicenseBlob) {
        sharedPrefs.edit().putString("license_blob", gson.toJson(blob)).commit()
    }

    fun getLicenseBlob(): LicenseBlob? {
        val json = sharedPrefs.getString("license_blob", null) ?: return null
        return try {
            gson.fromJson(json, LicenseBlob::class.java)
        } catch (e: Exception) {
            sharedPrefs.edit()
                .putString("license_blob.corrupt", json)
                .remove("license_blob")
                .apply()
            null
        }
    }
    
    fun saveVpnProfile(profile: VpnProfileDto) {
        sharedPrefs.edit().putString("vpn_profile", gson.toJson(profile)).commit()
    }

    fun getVpnProfile(): VpnProfileDto? {
        val json = sharedPrefs.getString("vpn_profile", null) ?: return null
        return try {
            gson.fromJson(json, VpnProfileDto::class.java)
        } catch (e: Exception) {
            sharedPrefs.edit()
                .putString("vpn_profile.corrupt", json)
                .remove("vpn_profile")
                .apply()
            null
        }
    }

    fun saveLastTrustedTimestamp(timestampMs: Long) {
        sharedPrefs.edit().putLong("last_trusted_timestamp", timestampMs).commit()
    }

    fun getLastTrustedTimestamp(): Long? {
        if (!sharedPrefs.contains("last_trusted_timestamp")) return null
        return sharedPrefs.getLong("last_trusted_timestamp", 0L)
    }

    fun getDeviceGuid(): String {
        var guid = sharedPrefs.getString("device_guid", null)
        if (guid == null) {
            guid = java.util.UUID.randomUUID().toString()
            sharedPrefs.edit().putString("device_guid", guid).commit()
        }
        return guid
    }

    fun clearDeviceGuid() {
        sharedPrefs.edit().remove("device_guid").commit()
    }

    fun clearAll() {
        sharedPrefs.edit().clear().commit()
    }
}
