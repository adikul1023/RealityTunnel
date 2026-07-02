#!/usr/bin/env python3
"""
Test 07 — Core Restart
Phase 0.3: Marzban Runtime Validation

Measures Xray core restart time via POST /api/core/restart and verifies
that users and inbounds survive the restart intact.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import (
    ADMIN_PASS,
    ADMIN_USER,
    CleanupGuard,
    LogWindow,
    MarzbanClient,
    Result,
    client_required,
    note,
    section,
    step,
    warn,
)

TEST_USER = "poc_t07"


def _inbound_tag_exists(inbounds: object, tag: str) -> bool:
    """Return True if an inbound with *tag* appears anywhere in the inbounds dict."""
    if not isinstance(inbounds, dict):
        return False
    for _proto, ibs in inbounds.items():
        if isinstance(ibs, list):
            for ib in ibs:
                if isinstance(ib, dict) and ib.get("tag") == tag:
                    return True
    return False


def run() -> bool:
    r = Result("Test 07 — Core Restart")
    c = MarzbanClient()

    # ── Step 1: Create test user ──────────────────────────────────────────────
    section("Setup")
    step(f"Creating test user {TEST_USER} (VLESS TCP REALITY, active)")
    status, body = c.create_user(TEST_USER)
    if not r.check(f"User {TEST_USER} created", status == 200, f"HTTP {status}"):
        return r.summary()

    with CleanupGuard(c, TEST_USER):
        # ── Step 2: Pre-restart core state ────────────────────────────────────
        section("Pre-restart state")
        step("GET /api/core")
        s, core_data = c.get_core()
        r.check("GET /api/core returned 200", s == 200, f"HTTP {s}")
        pre_version = (
            core_data.get("version", "unknown")
            if isinstance(core_data, dict)
            else "unknown"
        )
        pre_started = (
            core_data.get("started", False) if isinstance(core_data, dict) else False
        )
        r.check("Core is started before restart", pre_started)
        note(f"Xray version  : {pre_version}")
        note(f"started flag  : {pre_started}")

        # ── Steps 3–6: LogWindow + restart + poll ─────────────────────────────
        section("Core restart")
        restart_duration_s = 0.0
        restarted = False

        # Step 3: open log window before the restart
        with LogWindow() as lw:
            # Step 4: trigger restart
            step("POST /api/core/restart")
            restart_start = time.time()
            status, _ = c.restart_core()
            r.check(
                "POST /api/core/restart returned HTTP 200",
                status == 200,
                f"HTTP {status}",
            )

            # Step 5: poll until started==True
            step("Polling GET /api/core every 0.5s until started==True (timeout 30s)")
            deadline = restart_start + 30.0
            while time.time() < deadline:
                time.sleep(0.5)
                s, core_data = c.get_core()
                if (
                    s == 200
                    and isinstance(core_data, dict)
                    and core_data.get("started") is True
                ):
                    restarted = True
                    break
            restart_duration_s = round(time.time() - restart_start, 2)

            # Step 6: assert within 30s
            r.check(
                f"Core restarted within 30s ({restart_duration_s}s elapsed)",
                restarted,
            )
            r.measure("restart_duration_s", restart_duration_s)

            # Step 7: log verification
            section("Log verification")
            step("Checking container logs for restart events")
            time.sleep(1.0)  # brief pause to allow log lines to flush
            note("New log lines since restart:")
            lw.print_new()

            stopped_in_log = lw.contains("Xray core stopped")
            started_in_log = lw.contains("Xray core 24.12.31 started")
            r.check("Logs contain 'Xray core stopped'", stopped_in_log)
            r.check("Logs contain 'Xray core 24.12.31 started'", started_in_log)

        # ── Steps 8–9: Post-restart assertions ───────────────────────────────
        section("Post-restart assertions")

        # Step 8: user survival
        step(f"GET /api/user/{TEST_USER} — user survival check")
        s, user_data = c.get_user(TEST_USER)
        user_survived = s == 200
        user_active = (
            (isinstance(user_data, dict) and user_data.get("status") == "active")
            if user_survived
            else False
        )
        r.check(
            f"User {TEST_USER} still exists after restart", user_survived, f"HTTP {s}"
        )
        r.check(f"User {TEST_USER} status still 'active'", user_active)
        r.measure("user_survived", user_survived)

        # Step 9: inbound survival
        step("GET /api/inbounds — inbound survival check")
        s, inbounds = c.get_inbounds()
        r.check("GET /api/inbounds returned 200", s == 200, f"HTTP {s}")
        inbound_survived = (
            _inbound_tag_exists(inbounds, "VLESS TCP REALITY") if s == 200 else False
        )
        r.check(
            "'VLESS TCP REALITY' inbound still present after restart", inbound_survived
        )
        r.measure("inbound_survived", inbound_survived)

        # Step 11: client note
        client_required(
            "Any active VPN connection drops when the core restarts. "
            "Client must reconnect. Auto-retry in sing-box will succeed immediately "
            "since the user is re-added to Xray during restart."
        )

    # Step 12: cleanup handled by CleanupGuard.__exit__
    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
