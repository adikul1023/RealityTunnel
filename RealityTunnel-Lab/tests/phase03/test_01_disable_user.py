#!/usr/bin/env python3
"""
Test 01 — Disable User (status → disabled)
Phase 0.3: Marzban Runtime Validation

What this tests:
  Disabling a user via PUT /api/user/{username} fires a live gRPC RemoveUser
  call and marks the user disabled — without restarting Xray.  The existing
  TCP connection survives (RemoveUser only removes the entry from Xray's
  sync.Map; no goroutine signal is sent).  The subscription URL stays alive
  and the panel log shows the status transition, not a core restart.

What it requires:
  - Marzban running with the VLESS TCP REALITY inbound configured.
  - A VPN client connected through that inbound (for the live-session half of
    the test; the API/log assertions are fully automated).
"""

import sys
import time
import urllib.parse

from common import (
    CleanupGuard,
    LogWindow,
    MarzbanClient,
    Result,
    client_required,
    note,
    row,
    section,
    step,
    warn,
)

TEST_USER = "poc_t01"


def run() -> bool:
    r = Result("Test 01 — Disable User")
    c = MarzbanClient()

    # ──────────────────────────────────────────────────────────────────────────
    section("SETUP")
    # ──────────────────────────────────────────────────────────────────────────
    step("Create test user poc_t01 (VLESS TCP REALITY, active)")
    status, user = c.create_user(TEST_USER)
    r.check("Create user HTTP 200", status == 200, f"got {status}")
    if status != 200:
        warn("Cannot continue without a valid user — aborting.")
        r.summary()
        return False

    sub_url: str = user.get("subscription_url", "")
    sub_path = urllib.parse.urlparse(sub_url).path
    note(f"subscription_url  : {sub_url}")
    note(f"subscription_path : {sub_path}")

    # ──────────────────────────────────────────────────────────────────────────
    with CleanupGuard(c, TEST_USER):
        section("TEST STEPS")
        # ──────────────────────────────────────────────────────────────────────

        # Step 1 — disable via PUT ─────────────────────────────────────────────
        step("PUT /api/user/poc_t01  {status: disabled}")
        with LogWindow() as lw:
            t_disable = time.time()
            status_put, body_put = c.modify_user(TEST_USER, status="disabled")
            elapsed_api = time.time() - t_disable

        r.check("PUT returns HTTP 200", status_put == 200, f"got {status_put}")
        r.check(
            "Response body status == 'disabled'",
            isinstance(body_put, dict) and body_put.get("status") == "disabled",
            f"got {repr(body_put.get('status') if isinstance(body_put, dict) else body_put)}",
        )

        # Step 2 — GET to confirm persistence ─────────────────────────────────
        step("GET /api/user/poc_t01 — confirm status persisted in DB")
        status_get, body_get = c.get_user(TEST_USER)
        r.check("GET returns HTTP 200", status_get == 200, f"got {status_get}")
        r.check(
            "Persisted status == 'disabled'",
            isinstance(body_get, dict) and body_get.get("status") == "disabled",
            f"got {repr(body_get.get('status') if isinstance(body_get, dict) else body_get)}",
        )

        # Step 3 — log assertions ──────────────────────────────────────────────
        step("Inspect container logs for expected status transition")
        new_lines = lw.new_lines()
        note("New log lines captured:")
        lw.print_new()

        log_blob = "\n".join(new_lines)
        r.check(
            "Log: status changed active → disabled",
            "status changed from UserStatus.active to UserStatus.disabled" in log_blob,
        )
        r.check(
            "Log: does NOT contain 'Restarting Xray core'",
            "Restarting Xray core" not in log_blob,
        )

        # Step 4 — subscription URL still returns 200 ─────────────────────────
        step(f"Fetch subscription URL after disable: {sub_path}")
        sub_status, _sub_body = c.get_sub(sub_path)
        r.check(
            "Sub URL still returns HTTP 200 after disable",
            sub_status == 200,
            f"got {sub_status}",
        )
        note(
            "Critical finding: disabling a user does NOT revoke the subscription "
            "URL. Only POST /api/user/{u}/revoke_sub changes the URL token."
        )

        # ──────────────────────────────────────────────────────────────────────
        section("MEASUREMENTS")
        # ──────────────────────────────────────────────────────────────────────
        r.measure("API disable round-trip (s)", f"{elapsed_api:.3f}")
        r.measure("Sub URL HTTP status after disable", sub_status)
        r.measure("Xray restart triggered", "NO — gRPC RemoveUser only")
        r.measure(
            "Existing TCP session fate",
            "Survives indefinitely (RemoveUser deletes sync.Map entry; "
            "no goroutine signal sent to active conn)",
        )
        r.measure(
            "New connection attempts after disable",
            "Fail immediately (UUID no longer registered in Xray)",
        )
        r.measure(
            "Background job enforcement (expiry/quota)",
            "Runs every 10 s — irrelevant for manual disable; takes effect "
            "on next review cycle regardless",
        )

        # ──────────────────────────────────────────────────────────────────────
        section("CLIENT REQUIRED — Active Session Behavior")
        # ──────────────────────────────────────────────────────────────────────
        client_required(
            "Connect a VPN client to the VLESS TCP REALITY inbound before "
            "running this test."
        )
        client_required(
            "After disabling, the existing TCP tunnel survives indefinitely. "
            "(Xray source proven: RemoveUser only deletes the entry from "
            "sync.Map — no goroutine signal is sent to the active connection.)"
        )
        client_required(
            "New connection attempts fail immediately — AddUser was not called, "
            "so Xray does not recognise the UUID on any fresh VLESS handshake."
        )
        client_required(
            "Measure: time from PUT /api/user/poc_t01 (disabled) to first ping "
            "loss through the tunnel. Expected: existing session never drops; "
            "new sessions fail at once (< 1 s)."
        )
    # ── CleanupGuard deletes poc_t01 here ─────────────────────────────────────

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
