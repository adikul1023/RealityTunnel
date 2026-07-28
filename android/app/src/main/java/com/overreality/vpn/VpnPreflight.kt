package com.overreality.vpn

import android.content.Context
import java.net.InetSocketAddress
import java.net.Socket

object VpnPreflight {
    private val UUID_REGEX = Regex(
        "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
    )

    // REALITY public keys are typically URL-safe base64-ish strings around 43-44 chars.
    private val REALITY_KEY_REGEX = Regex("^[A-Za-z0-9_-]{40,60}$")

    // Accept IPv4 or hostname characters only; prevents accidental pasted status text.
    private val SERVER_HOST_REGEX = Regex("^[A-Za-z0-9.-]{1,253}$")

    data class Result(val ok: Boolean, val message: String)

    private fun canReach(serverIp: String, timeoutMs: Int): Result {
        return try {
            Socket().use { s ->
                s.connect(InetSocketAddress(serverIp, 443), timeoutMs)
            }
            Result(true, "Preflight OK: server:443 reachable")
        } catch (e: Exception) {
            Result(false, "Cannot reach $serverIp:443 (${e.message})")
        }
    }

    fun run(context: Context, serverIp: String): Result {
        val prefs = VpnConfigStore.prefs(context)
        val uuid = prefs.getString(VpnConfigStore.KEY_UUID, "")?.trim().orEmpty()
        val pubKey = prefs.getString(VpnConfigStore.KEY_PUBLIC_KEY, "")?.trim().orEmpty()

        if (serverIp.isBlank()) return Result(false, "Server IP is empty")
        if (!SERVER_HOST_REGEX.matches(serverIp)) {
            return Result(false, "Server IP/host format invalid")
        }
        if (uuid.isBlank()) return Result(false, "UUID is empty")
        if (pubKey.isBlank()) return Result(false, "REALITY public key is empty")

        if (!UUID_REGEX.matches(uuid)) {
            return Result(false, "UUID format looks invalid")
        }

        if (!REALITY_KEY_REGEX.matches(pubKey)) {
            return Result(false, "REALITY public key format looks invalid")
        }

        // Basic network reachability check before enabling VPN.
        // Retry once with a longer timeout to reduce transient false negatives.
        val first = canReach(serverIp, 4000)
        if (first.ok) return first

        val second = canReach(serverIp, 7000)
        if (second.ok) return Result(true, "Preflight OK on retry: server:443 reachable")

        return second
    }
}
