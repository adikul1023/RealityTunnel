package com.overreality.vpn

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class VpnProfile(
    val id: String,
    val name: String,
    val serverIp: String,
    val uuid: String,
    val publicKey: String,
    val sni: String,
    val shortId: String,
)

object VpnConfigStore {
    private const val PREFS = "overreality_prefs"
    private const val KEY_PROFILES_JSON = "vpn_profiles_json"
    private const val KEY_ACTIVE_PROFILE_ID = "vpn_active_profile_id"
    private const val KEY_SETUP_COMPLETE = "vpn_setup_complete"

    const val KEY_SERVER_IP = "vpn_server_ip"
    const val KEY_UUID = "vpn_uuid"
    const val KEY_PUBLIC_KEY = "vpn_public_key"
    const val KEY_SNI = "vpn_sni"
    const val KEY_SHORT_ID = "vpn_short_id"

    fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun listProfiles(context: Context): List<VpnProfile> {
        val prefs = prefs(context)
        migrateLegacyConfigIfNeeded(prefs)
        val raw = prefs.getString(KEY_PROFILES_JSON, "[]").orEmpty()
        val array = JSONArray(raw)
        return buildList {
            for (index in 0 until array.length()) {
                val item = array.optJSONObject(index) ?: continue
                add(item.toProfile())
            }
        }
    }

    fun getActiveProfile(context: Context): VpnProfile? {
        val prefs = prefs(context)
        migrateLegacyConfigIfNeeded(prefs)
        val activeId = prefs.getString(KEY_ACTIVE_PROFILE_ID, null)
        val profiles = listProfiles(context)
        return profiles.firstOrNull { it.id == activeId } ?: profiles.firstOrNull()
    }

    fun setActiveProfile(context: Context, profileId: String) {
        val prefs = prefs(context)
        val profiles = listProfiles(context)
        val profile = profiles.firstOrNull { it.id == profileId } ?: return
        prefs.edit()
            .putString(KEY_ACTIVE_PROFILE_ID, profile.id)
            .putBoolean(KEY_SETUP_COMPLETE, true)
            .applyActiveProfile(profile)
            .apply()
    }

    fun saveProfile(context: Context, profile: VpnProfile, makeActive: Boolean = true): VpnProfile {
        val prefs = prefs(context)
        val existing = listProfiles(context).toMutableList()
        val sanitized = profile.copy(
            id = profile.id.ifBlank { UUID.randomUUID().toString() },
            name = profile.name.ifBlank { defaultProfileName(existing.size) },
            serverIp = profile.serverIp.trim(),
            uuid = profile.uuid.trim(),
            publicKey = profile.publicKey.trim(),
            sni = profile.sni.trim(),
            shortId = profile.shortId.trim(),
        )
        val index = existing.indexOfFirst { it.id == sanitized.id }
        if (index >= 0) {
            existing[index] = sanitized
        } else {
            existing += sanitized
        }

        val editor = prefs.edit()
            .putString(KEY_PROFILES_JSON, JSONArray().apply {
                existing.forEach { put(it.toJson()) }
            }.toString())
            .putBoolean(KEY_SETUP_COMPLETE, true)

        if (makeActive || prefs.getString(KEY_ACTIVE_PROFILE_ID, null) == null) {
            editor.putString(KEY_ACTIVE_PROFILE_ID, sanitized.id)
            editor.applyActiveProfile(sanitized)
        }

        editor.apply()
        return sanitized
    }

    fun deleteProfile(context: Context, profileId: String) {
        val prefs = prefs(context)
        val existing = listProfiles(context).toMutableList()
        val removed = existing.firstOrNull { it.id == profileId } ?: return
        existing.removeAll { it.id == profileId }

        val editor = prefs.edit()
            .putString(KEY_PROFILES_JSON, JSONArray().apply {
                existing.forEach { put(it.toJson()) }
            }.toString())

        val nextActive = when {
            prefs.getString(KEY_ACTIVE_PROFILE_ID, null) != removed.id -> {
                existing.firstOrNull { it.id == prefs.getString(KEY_ACTIVE_PROFILE_ID, null) }
            }
            else -> existing.firstOrNull()
        }

        if (nextActive != null) {
            editor.putString(KEY_ACTIVE_PROFILE_ID, nextActive.id)
                .putBoolean(KEY_SETUP_COMPLETE, true)
                .applyActiveProfile(nextActive)
        } else {
            editor.remove(KEY_ACTIVE_PROFILE_ID)
                .remove(KEY_SERVER_IP)
                .remove(KEY_UUID)
                .remove(KEY_PUBLIC_KEY)
                .remove(KEY_SNI)
                .remove(KEY_SHORT_ID)
                .putBoolean(KEY_SETUP_COMPLETE, false)
        }

        editor.apply()
    }

    fun hasCompletedSetup(context: Context): Boolean {
        val prefs = prefs(context)
        migrateLegacyConfigIfNeeded(prefs)
        return prefs.getBoolean(KEY_SETUP_COMPLETE, false) && listProfiles(context).isNotEmpty()
    }

    private fun migrateLegacyConfigIfNeeded(prefs: android.content.SharedPreferences) {
        if (prefs.contains(KEY_PROFILES_JSON)) return

        val uuid = prefs.getString(KEY_UUID, "").orEmpty().trim()
        val publicKey = prefs.getString(KEY_PUBLIC_KEY, "").orEmpty().trim()
        val serverIp = prefs.getString(KEY_SERVER_IP, "").orEmpty().trim()
        val sni = prefs.getString(KEY_SNI, "www.microsoft.com").orEmpty().trim()
        val shortId = prefs.getString(KEY_SHORT_ID, "").orEmpty().trim()

        if (uuid.isBlank() && publicKey.isBlank() && serverIp.isBlank()) {
            prefs.edit()
                .putString(KEY_PROFILES_JSON, "[]")
                .putBoolean(KEY_SETUP_COMPLETE, false)
                .apply()
            return
        }

        val profile = VpnProfile(
            id = UUID.randomUUID().toString(),
            name = "Primary",
            serverIp = serverIp,
            uuid = uuid,
            publicKey = publicKey,
            sni = sni.ifBlank { "www.microsoft.com" },
            shortId = shortId,
        )

        prefs.edit()
            .putString(KEY_PROFILES_JSON, JSONArray().put(profile.toJson()).toString())
            .putString(KEY_ACTIVE_PROFILE_ID, profile.id)
            .putBoolean(KEY_SETUP_COMPLETE, serverIp.isNotBlank() && uuid.isNotBlank() && publicKey.isNotBlank())
            .applyActiveProfile(profile)
            .apply()
    }

    private fun defaultProfileName(index: Int): String = "Config ${index + 1}"

    private fun JSONObject.toProfile(): VpnProfile {
        return VpnProfile(
            id = optString("id"),
            name = optString("name"),
            serverIp = optString("serverIp"),
            uuid = optString("uuid"),
            publicKey = optString("publicKey"),
            sni = optString("sni", "www.microsoft.com"),
            shortId = optString("shortId"),
        )
    }

    private fun VpnProfile.toJson(): JSONObject {
        return JSONObject()
            .put("id", id)
            .put("name", name)
            .put("serverIp", serverIp)
            .put("uuid", uuid)
            .put("publicKey", publicKey)
            .put("sni", sni)
            .put("shortId", shortId)
    }

    private fun android.content.SharedPreferences.Editor.applyActiveProfile(profile: VpnProfile): android.content.SharedPreferences.Editor {
        return putString(KEY_SERVER_IP, profile.serverIp)
            .putString(KEY_UUID, profile.uuid)
            .putString(KEY_PUBLIC_KEY, profile.publicKey)
            .putString(KEY_SNI, profile.sni)
            .putString(KEY_SHORT_ID, profile.shortId)
    }
}
