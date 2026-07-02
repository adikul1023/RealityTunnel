#!/usr/bin/env python3
"""
Test 09 — Admin Token Behavior
Phase 0.3: Marzban Runtime Validation

Validates JWT structure, TTL, all credential failure modes, re-authentication,
and confirms there is no refresh endpoint.
This matters because the Billing server calls POST /api/admin/token repeatedly.
"""

import base64
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import (
    ADMIN_PASS,
    ADMIN_USER,
    MarzbanClient,
    Result,
    decode_jwt,
    note,
    section,
    step,
    wait_next_second,
    warn,
)


def _b64url_encode(data: bytes) -> str:
    """Base64url-encode *data* with no padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode_jwt_header(token: str) -> dict:
    """Decode the header (first segment) of a JWT without verification."""
    parts = token.split(".")
    if not parts:
        return {}
    pad = parts[0] + "=" * (-len(parts[0]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(pad))
    except Exception:
        return {}


def run() -> bool:
    r = Result("Test 09 — Admin Token Behavior")
    c = MarzbanClient()

    # ── Step 1: Obtain a fresh token, measure timing ──────────────────────────
    section("Token acquisition")
    step("POST /api/admin/token — obtaining fresh token")
    token_start = time.time()
    status, body = c.raw_login(ADMIN_USER, ADMIN_PASS)
    token_elapsed_ms = round((time.time() - token_start) * 1000, 1)

    r.check("POST /api/admin/token returned HTTP 200", status == 200, f"HTTP {status}")
    if status != 200:
        return r.summary()

    fresh_token = body.get("access_token", "") if isinstance(body, dict) else ""
    r.check("Response contains access_token field", bool(fresh_token))
    note(f"Token acquired in {token_elapsed_ms}ms")
    c.token = fresh_token  # ensure client holds this exact token for step 3

    # ── Step 2: Decode and inspect JWT payload + header ───────────────────────
    section("JWT structure analysis")
    step("Decoding JWT header (algorithm) and payload (claims)")

    header = _decode_jwt_header(fresh_token)
    payload = decode_jwt(fresh_token)

    alg = header.get("alg", "unknown")
    sub = payload.get("sub", "")
    access = payload.get("access", "")
    iat = payload.get("iat", 0)
    exp = payload.get("exp", 0)
    ttl_seconds = exp - iat
    ttl_hours = ttl_seconds / 3600
    expires_at = (
        time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(exp)) if exp else "unknown"
    )

    note(f"Algorithm (header.alg) : {alg}")
    note(f"sub                    : {sub}")
    note(f"access                 : {access}")
    note(f"iat                    : {iat}")
    note(f"exp                    : {exp}")
    note(f"TTL                    : {ttl_seconds}s ({ttl_hours:.1f}h)")
    note(f"Expires at             : {expires_at}")

    r.check("JWT algorithm is HS256", alg == "HS256", f"got '{alg}'")
    r.check("JWT sub == 'admin'", sub == "admin", f"got '{sub}'")
    r.check("JWT access == 'sudo'", access == "sudo", f"got '{access}'")
    r.check("JWT iat is set (non-zero)", iat > 0, f"iat={iat}")
    r.check("JWT exp is set (non-zero)", exp > 0, f"exp={exp}")
    r.check(
        "JWT TTL == 86400s (24h — no refresh needed within a day)",
        ttl_seconds == 86400,
        f"got {ttl_seconds}s ({ttl_hours:.2f}h)",
    )
    r.measure("jwt_algorithm", alg)
    r.measure("token_ttl_seconds", ttl_seconds)
    r.measure("token_ttl_hours", round(ttl_hours, 2))
    r.measure("token_expires_at", expires_at)

    # ── Step 3: Verify the token actually works ───────────────────────────────
    section("Token validation — success case")
    step("GET /api/admin with valid token")
    s, _ = c.authed_get("/api/admin", fresh_token)
    r.check("GET /api/admin with valid token → HTTP 200", s == 200, f"HTTP {s}")

    # ── Step 4: Wrong password ────────────────────────────────────────────────
    section("Failure modes")
    step("POST /api/admin/token — wrong password")
    s, resp = c.raw_login(ADMIN_USER, "wrongpassword")
    r.check("Wrong password → HTTP 401", s == 401, f"HTTP {s}")
    note(f"Response body: {json.dumps(resp) if isinstance(resp, dict) else repr(resp)}")
    r.measure("wrong_password_status", s)

    # ── Step 5: Wrong username ────────────────────────────────────────────────
    step("POST /api/admin/token — wrong username ('nobody')")
    s, _ = c.raw_login("nobody", ADMIN_PASS)
    r.check("Wrong username → HTTP 401", s == 401, f"HTTP {s}")
    r.measure("wrong_username_status", s)

    # ── Step 6: Missing token (empty Bearer value) ────────────────────────────
    step("GET /api/admin — empty Authorization token")
    s, _ = c.authed_get("/api/admin", "")
    r.check("Missing token → HTTP 401 or 403", s in (401, 403), f"HTTP {s}")
    r.measure("missing_auth_status", s)

    # ── Step 7: Malformed token (not a valid JWT) ─────────────────────────────
    step("GET /api/admin — malformed token ('this.is.garbage')")
    s, _ = c.authed_get("/api/admin", "this.is.garbage")
    r.check("Malformed token → HTTP 401 or 403", s in (401, 403), f"HTTP {s}")
    r.measure("malformed_token_status", s)

    # ── Step 8: Crafted token with exp in the past (1970-01-01) ──────────────
    step("GET /api/admin — crafted token with exp=1 (epoch 1970-01-01)")
    fake_header_b64 = _b64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    )
    fake_payload_b64 = _b64url_encode(
        json.dumps({"sub": "admin", "access": "sudo", "iat": 1, "exp": 1}).encode()
    )
    crafted_token = f"{fake_header_b64}.{fake_payload_b64}.fakesignature"
    note(f"Crafted token: {crafted_token[:60]}…")
    s, _ = c.authed_get("/api/admin", crafted_token)
    r.check("Expired/tampered token → HTTP 401 or 403", s in (401, 403), f"HTTP {s}")
    r.measure("expired_token_status", s)

    # ── Step 9: Re-authentication — new token must be issued ─────────────────
    section("Re-authentication")
    step("Calling c._login() again — expecting a new, distinct token")
    old_token = c.token
    wait_next_second()  # JWT iat is second-granular; same second ⇒ same token
    c._login(ADMIN_USER, ADMIN_PASS)
    new_token = c.token
    r.check("Re-login succeeded (token non-empty)", bool(new_token))
    r.check(
        "New token differs from old token (iat advances each call)",
        new_token != old_token,
    )

    # ── Step 10: Verify there is NO refresh endpoint ──────────────────────────
    section("No refresh endpoint")
    note(
        "Marzban has no token-refresh endpoint — re-authentication is the only renewal path."
    )

    step("GET /api/admin/refresh — expect 404 or 405")
    s, _ = c.get("/api/admin/refresh")
    no_get_refresh = s in (404, 405, 422)
    r.check(
        "GET /api/admin/refresh → 404/405/422 (not found)",
        no_get_refresh,
        f"HTTP {s}",
    )

    step("POST /api/admin/token/refresh — expect 404 or 405")
    s, _ = c.post("/api/admin/token/refresh")
    no_post_refresh = s in (404, 405, 422)
    r.check(
        "POST /api/admin/token/refresh → 404/405/422 (not found)",
        no_post_refresh,
        f"HTTP {s}",
    )

    no_refresh_endpoint = no_get_refresh and no_post_refresh
    r.measure("no_refresh_endpoint", no_refresh_endpoint)
    note("Re-authentication is the only token renewal mechanism.")

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
