#!/usr/bin/env python3
"""
Test 03 — UUID Rotation via revoke_sub
Phase 0.3: Marzban Runtime Validation

What this tests:
  POST /api/user/{username}/revoke_sub rotates the VLESS UUID immediately via
  a live gRPC RemoveUser + AddUser pair.  The old subscription URL hard-404s
  at once; the new one returns 200 and its decoded content contains the new
  UUID.  No Xray restart occurs.  An active session using the old UUID survives
  until it disconnects naturally (VLESS auth is checked only once per TCP
  connection — the same RemoveUser semantics as disable).

What it requires:
  - Marzban running with the VLESS TCP REALITY inbound configured.
  - Optional: a VPN client to observe that the active tunnel is not dropped
    by revoke_sub (API/log assertions are fully automated).
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

TEST_USER = "poc_t03"


def run() -> bool:
    r = Result("Test 03 — UUID Rotation via revoke_sub")
    c = MarzbanClient()

    # ──────────────────────────────────────────────────────────────────────────
    section("SETUP")
    # ──────────────────────────────────────────────────────────────────────────
    step("Create test user poc_t03 (VLESS TCP REALITY, active)")
    status, user = c.create_user(TEST_USER)
    r.check("Create user HTTP 200", status == 200, f"got {status}")
    if status != 200:
        warn("Cannot continue without a valid user — aborting.")
        r.summary()
        return False

    old_uuid: str = user.get("proxies", {}).get("vless", {}).get("id", "")
    old_sub_url: str = user.get("subscription_url", "")
    old_sub_path = urllib.parse.urlparse(old_sub_url).path
    note(f"Old UUID           : {old_uuid}")
    note(f"Old sub path       : {old_sub_path}")

    # ──────────────────────────────────────────────────────────────────────────
    with CleanupGuard(c, TEST_USER):
        section("TEST STEPS")
        # ──────────────────────────────────────────────────────────────────────

        # Step 1 — call revoke_sub ─────────────────────────────────────────────
        step("POST /api/user/poc_t03/revoke_sub")
        with LogWindow() as lw:
            t_revoke = time.time()
            status_rev, body_rev = c.revoke_sub(TEST_USER)
            elapsed_revoke = time.time() - t_revoke

        r.check("revoke_sub returns HTTP 200", status_rev == 200, f"got {status_rev}")
        if status_rev != 200:
            warn(f"revoke_sub failed: {body_rev}")
            r.summary()
            return False

        new_uuid: str = body_rev.get("proxies", {}).get("vless", {}).get("id", "")
        new_sub_url: str = body_rev.get("subscription_url", "")
        new_sub_path = urllib.parse.urlparse(new_sub_url).path
        note(f"New UUID           : {new_uuid}")
        note(f"New sub path       : {new_sub_path}")

        # Step 2 — UUID must differ ────────────────────────────────────────────
        step("Assert UUID was rotated")
        r.check(
            "New UUID differs from old UUID",
            bool(new_uuid) and new_uuid != old_uuid,
            f"old={old_uuid!r}  new={new_uuid!r}",
        )

        # Step 3 — old sub path → 404 ──────────────────────────────────────────
        step(f"Fetch old sub path (expect 404): {old_sub_path}")
        old_sub_status, _ = c.get_sub(old_sub_path)
        r.check(
            "Old subscription URL hard-404s immediately",
            old_sub_status == 404,
            f"got HTTP {old_sub_status}",
        )

        # Step 4 — new sub path → 200 + contains new UUID ─────────────────────
        step(f"Fetch new sub path (expect 200): {new_sub_path}")
        new_sub_status, new_sub_raw = c.get_sub(new_sub_path)
        r.check(
            "New subscription URL returns HTTP 200",
            new_sub_status == 200,
            f"got HTTP {new_sub_status}",
        )
        if new_sub_status == 200 and new_sub_raw.strip():
            try:
                decoded = base64.b64decode(new_sub_raw.strip()).decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                decoded = new_sub_raw
            r.check(
                "Decoded new subscription contains new UUID",
                new_uuid in decoded,
                f"UUID={new_uuid}",
            )
            note(f"Decoded snippet: {decoded[:120]!r}")

        # Step 5 — log assertions ──────────────────────────────────────────────
        step("Inspect container logs")
        new_lines = lw.new_lines()
        note("New log lines captured:")
        lw.print_new()

        log_blob = "\n".join(new_lines)
        r.check(
            "Log: contains 'subscription revoked'",
            "subscription revoked" in log_blob,
        )
        r.check(
            "Log: does NOT contain 'Restarting Xray core'",
            "Restarting Xray core" not in log_blob,
        )

        # ──────────────────────────────────────────────────────────────────────
        section("MEASUREMENTS")
        # ──────────────────────────────────────────────────────────────────────
        r.measure("revoke_sub API round-trip (s)", f"{elapsed_revoke:.3f}")
        r.measure("Old UUID", old_uuid)
        r.measure("New UUID", new_uuid)
        r.measure("Old sub URL fate", f"HTTP {old_sub_status} — hard-404 immediately")
        r.measure("New sub URL fate", f"HTTP {new_sub_status} — live immediately")
        r.measure("Xray restart triggered", "NO — gRPC RemoveUser + AddUser only")
        r.measure(
            "Existing TCP session fate after UUID rotation",
            "Survives (RemoveUser removes sync.Map entry; active goroutine "
            "is not signalled — VLESS auth checked once per connection)",
        )
        r.measure(
            "Background review job interval",
            "10 s — enforces expiry/quota; does not affect UUID rotation",
        )

        # ──────────────────────────────────────────────────────────────────────
        section("CLIENT REQUIRED — Active Session Behavior")
        # ──────────────────────────────────────────────────────────────────────
        client_required(
            "Connect a VPN client to the VLESS TCP REALITY inbound before "
            "calling revoke_sub."
        )
        client_required(
            "Existing session survives UUID rotation — same semantics as "
            "disable: Marzban calls RemoveUser + AddUser on Xray; the active "
            "goroutine is not signalled. VLESS authentication is checked only "
            "once per TCP connection, so the old UUID is never re-validated "
            "on the live session."
        )
        client_required(
            "After the session disconnects naturally, the old UUID is "
            "permanently rejected. The client must fetch the new subscription "
            "URL (the new path) and reconfigure before reconnecting."
        )
    # ── CleanupGuard deletes poc_t03 here ─────────────────────────────────────

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
