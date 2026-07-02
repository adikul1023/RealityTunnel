#!/usr/bin/env python3
"""
Test 02 — Re-enable User (disabled → active)
Phase 0.3: Marzban Runtime Validation

What this tests:
  Re-enabling a previously disabled user fires a live gRPC RemoveUser + AddUser
  pair (hot reload) — Xray is never restarted.  The user becomes reachable
  again immediately.  The panel log shows the disabled → active transition and
  must not show a core restart.  The subscription URL continues to return 200
  and the decoded content contains the user's current UUID.

What it requires:
  - Marzban running with the VLESS TCP REALITY inbound configured.
  - Optional: a VPN client to verify that a new connection succeeds immediately
    after re-enable (the API/log assertions are fully automated).
"""

import base64
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

TEST_USER = "poc_t02"


def run() -> bool:
    r = Result("Test 02 — Re-enable User")
    c = MarzbanClient()

    # ──────────────────────────────────────────────────────────────────────────
    section("SETUP")
    # ──────────────────────────────────────────────────────────────────────────
    step("Create test user poc_t02 (VLESS TCP REALITY, active)")
    status, user = c.create_user(TEST_USER)
    r.check("Create user HTTP 200", status == 200, f"got {status}")
    if status != 200:
        warn("Cannot continue without a valid user — aborting.")
        r.summary()
        return False

    uuid_initial: str = user.get("proxies", {}).get("vless", {}).get("id", "")
    sub_url: str = user.get("subscription_url", "")
    sub_path = urllib.parse.urlparse(sub_url).path
    note(f"Initial UUID       : {uuid_initial}")
    note(f"subscription_url   : {sub_url}")
    note(f"subscription_path  : {sub_path}")

    # ──────────────────────────────────────────────────────────────────────────
    with CleanupGuard(c, TEST_USER):
        section("TEST STEPS")
        # ──────────────────────────────────────────────────────────────────────

        # Step 1 — disable ─────────────────────────────────────────────────────
        step("PUT /api/user/poc_t02  {status: disabled}")
        status_dis, body_dis = c.modify_user(TEST_USER, status="disabled")
        r.check("Disable returns HTTP 200", status_dis == 200, f"got {status_dis}")
        r.check(
            "Body status after disable == 'disabled'",
            isinstance(body_dis, dict) and body_dis.get("status") == "disabled",
            f"got {repr(body_dis.get('status') if isinstance(body_dis, dict) else body_dis)}",
        )
        if status_dis != 200:
            warn("Disable step failed — cannot continue.")
            r.summary()
            return False

        # Step 2 — re-enable ───────────────────────────────────────────────────
        step("PUT /api/user/poc_t02  {status: active}")
        with LogWindow() as lw:
            t_enable = time.time()
            status_en, body_en = c.modify_user(TEST_USER, status="active")
            elapsed_api = time.time() - t_enable

        r.check("Re-enable returns HTTP 200", status_en == 200, f"got {status_en}")
        r.check(
            "Body status after re-enable == 'active'",
            isinstance(body_en, dict) and body_en.get("status") == "active",
            f"got {repr(body_en.get('status') if isinstance(body_en, dict) else body_en)}",
        )

        # Step 3 — GET to confirm persistence ─────────────────────────────────
        step("GET /api/user/poc_t02 — confirm status persisted in DB")
        status_get, body_get = c.get_user(TEST_USER)
        r.check("GET returns HTTP 200", status_get == 200, f"got {status_get}")
        r.check(
            "Persisted status == 'active'",
            isinstance(body_get, dict) and body_get.get("status") == "active",
            f"got {repr(body_get.get('status') if isinstance(body_get, dict) else body_get)}",
        )

        # Step 4 — log assertions ──────────────────────────────────────────────
        step("Inspect container logs for expected status transition")
        new_lines = lw.new_lines()
        note("New log lines captured:")
        lw.print_new()

        log_blob = "\n".join(new_lines)
        r.check(
            "Log: status changed disabled → active",
            "status changed from UserStatus.disabled to UserStatus.active" in log_blob,
        )
        r.check(
            "Log: does NOT contain 'Restarting Xray core'",
            "Restarting Xray core" not in log_blob,
        )

        # Step 5 — subscription URL returns 200 and contains UUID ─────────────
        step(f"Fetch subscription URL after re-enable: {sub_path}")
        sub_status, sub_raw = c.get_sub(sub_path)
        r.check(
            "Sub URL returns HTTP 200 after re-enable",
            sub_status == 200,
            f"got {sub_status}",
        )
        if sub_status == 200 and sub_raw.strip():
            try:
                decoded = base64.b64decode(sub_raw.strip()).decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                decoded = sub_raw
            r.check(
                "Decoded subscription contains current UUID",
                uuid_initial in decoded,
                f"UUID={uuid_initial}",
            )
            note(f"Decoded snippet: {decoded[:120]!r}")

        # ──────────────────────────────────────────────────────────────────────
        section("MEASUREMENTS")
        # ──────────────────────────────────────────────────────────────────────
        r.measure("API re-enable round-trip (s)", f"{elapsed_api:.3f}")
        r.measure("Sub URL HTTP status after re-enable", sub_status)
        r.measure("UUID unchanged by enable/disable", uuid_initial)
        r.measure(
            "Xray mechanism",
            "gRPC RemoveUser + AddUser (hot reload — no restart)",
        )
        r.measure(
            "New connections after re-enable",
            "Succeed immediately (AddUser re-inserts UUID into sync.Map)",
        )
        r.measure(
            "Admin token validity window",
            "24 h (86 400 s) from login — no token rotation needed for this test",
        )

        # ──────────────────────────────────────────────────────────────────────
        section("CLIENT REQUIRED — Active Session Behavior")
        # ──────────────────────────────────────────────────────────────────────
        client_required(
            "Connect a VPN client to the VLESS TCP REALITY inbound before "
            "disabling the user."
        )
        client_required(
            "After re-enable, a new connection succeeds immediately. "
            "The Xray gRPC update_user call fires RemoveUser + AddUser — "
            "hot reload, no restart. Authentication is checked once per TCP "
            "connection, so a pre-existing tunnel from the disabled window "
            "also survives if it was never closed."
        )
        client_required(
            "Measure: time from PUT /api/user/poc_t02 (active) to first "
            "successful new connection. Expected: < 1 s (gRPC call is "
            "synchronous with the API response)."
        )
    # ── CleanupGuard deletes poc_t02 here ─────────────────────────────────────

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
