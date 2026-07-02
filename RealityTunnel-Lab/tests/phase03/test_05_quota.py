#!/usr/bin/env python3
"""
Test 05 — Data Quota Enforcement
Phase 0.3: Marzban Runtime Validation

What this tests:
  - Setting data_limit via PUT is reflected immediately in the API response.
  - Enforcement (active → limited) is background-job-driven (review() every 10 s).
  - This test injects fake used_traffic directly into SQLite to simulate quota
    exhaustion without a real VPN client generating traffic.
  - Measures actual enforcement lag.

What it requires:
  - Marzban running in Docker with SQLite DB bound to workspace.
  - sqlite3 Python module (stdlib, always available).
  - No VPN client needed for server-side assertions.

Key facts:
  - review() job: used_traffic >= data_limit → status=limited, gRPC RemoveUser.
  - Marzban does NOT push quota to Xray — Xray has no quota concept.
  - Enforcement lag: up to ~10 s (background job interval).
  - data_limit=0 means UNLIMITED (not zero bytes).
"""

import sys
import time

from common import (
    CleanupGuard,
    LogWindow,
    MarzbanClient,
    Result,
    client_required,
    fail,
    note,
    ok,
    row,
    section,
    sqlite_exec,
    step,
    warn,
)

TEST_USER = "poc_t05"
DATA_LIMIT_BYTES = 1 * 1024 * 1024  # 1 MB limit set via API
INJECTED_BYTES = 2 * 1024 * 1024  # 2 MB injected into DB (exceeds limit)
WATCH_TIMEOUT_S = 90
POLL_INTERVAL_S = 2


def run() -> bool:
    r = Result("Test 05 — Data Quota Enforcement")
    c = MarzbanClient()

    # ── Part A: set data_limit via API ────────────────────────────────────

    section("PART A — Set data_limit via API")

    step("Create test user poc_t05")
    status, body = c.create_user(TEST_USER)
    r.check("create_user HTTP 200", status == 200)
    r.check(
        "initial status == active",
        body.get("status") == "active" if isinstance(body, dict) else False,
    )

    with CleanupGuard(c, TEST_USER):
        step(f"PUT data_limit={DATA_LIMIT_BYTES} bytes (1 MB)")
        status, body = c.modify_user(TEST_USER, data_limit=DATA_LIMIT_BYTES)
        r.check("PUT HTTP 200", status == 200)
        r.check(
            "data_limit reflected in response",
            body.get("data_limit") == DATA_LIMIT_BYTES
            if isinstance(body, dict)
            else False,
        )
        r.check(
            "status still active (under limit)",
            body.get("status") == "active" if isinstance(body, dict) else False,
        )
        r.measure("data_limit_bytes", DATA_LIMIT_BYTES)
        r.measure("data_limit_set_via_api", "Immediate — reflected in PUT response")

        step("GET user — verify data_limit persisted")
        status, body = c.get_user(TEST_USER)
        r.check("GET HTTP 200", status == 200)
        r.check(
            "data_limit persisted",
            body.get("data_limit") == DATA_LIMIT_BYTES
            if isinstance(body, dict)
            else False,
        )
        r.check(
            "used_traffic == 0 (no real traffic)",
            body.get("used_traffic") == 0 if isinstance(body, dict) else False,
        )

        # ── Part B: inject fake traffic ────────────────────────────────────

        section("PART B — Inject fake used_traffic into SQLite")

        step(f"Injecting {INJECTED_BYTES} bytes of fake used_traffic via sqlite_exec")
        note("This simulates quota exhaustion without needing a VPN client.")

        try:
            rows = sqlite_exec(
                "UPDATE users SET used_traffic=? WHERE username=? RETURNING username, used_traffic",
                (INJECTED_BYTES, TEST_USER),
            )
            if rows:
                r.check(
                    "DB update succeeded", True, f"used_traffic now {rows[0][1]} bytes"
                )
                r.measure("injected_used_traffic_bytes", INJECTED_BYTES)
            else:
                warn("UPDATE returned no rows — user not found in DB by username?")
                r.check("DB update returned rows", False)
        except Exception as e:
            warn(f"sqlite_exec error: {e}")
            r.check("sqlite_exec succeeded", False, str(e))

        # ── Part C: wait for review() job ─────────────────────────────────

        section("PART C — Wait for background job enforcement")

        step(
            f"Polling GET /api/user every {POLL_INTERVAL_S}s (up to {WATCH_TIMEOUT_S}s)..."
        )
        note("review() job runs every ~10 s and checks used_traffic >= data_limit.")

        detected_at = None
        inject_time = time.time()
        poll_count = 0

        with LogWindow() as lw:
            deadline = inject_time + WATCH_TIMEOUT_S
            while time.time() < deadline:
                _, u = c.get_user(TEST_USER)
                poll_count += 1
                if isinstance(u, dict) and u.get("status") == "limited":
                    detected_at = time.time()
                    break
                elapsed = time.time() - inject_time
                print(
                    f"\r     polling... ({elapsed:.0f}s since injection, polls: {poll_count})",
                    end="",
                    flush=True,
                )
                time.sleep(POLL_INTERVAL_S)

            print()

            step("Capture log evidence")
            lw.print_new()
            r.check(
                "log: status changed to UserStatus.limited",
                lw.contains("UserStatus.limited"),
            )
            r.check(
                "log: no Xray restart",
                not lw.contains("Restarting Xray core"),
            )

        if detected_at is None:
            fail(f"Status did not transition to 'limited' within {WATCH_TIMEOUT_S}s")
            r.failed += 1
            r.measure("quota_enforcement_lag_s", "TIMEOUT — not enforced within window")
        else:
            lag = detected_at - inject_time
            ok(f"Status transitioned to 'limited' {lag:.1f}s after traffic injection")
            r.passed += 1
            r.measure("quota_enforcement_lag_s", f"{lag:.1f}s after injection")
            r.measure("polls_until_detection", poll_count)
            r.check(
                "enforcement within 30s of injection",
                lag <= 30,
                f"actual lag: {lag:.1f}s",
            )

        step("Final GET — confirm state")
        _, final = c.get_user(TEST_USER)
        final_status = final.get("status") if isinstance(final, dict) else "?"
        r.check("final status == limited", final_status == "limited", final_status)

        step("Check: new connection blocked after limit hit")
        note(
            "Marzban called gRPC RemoveUser on VLESS TCP REALITY inbound. "
            "New connections using poc_t05's UUID will be rejected by Xray."
        )
        note(
            "Existing connections survive (same as disable/expiry — no goroutine kill)."
        )

    # ── Session behavior note ──────────────────────────────────────────────

    section("CLIENT REQUIRED — Active Session Behavior")
    client_required(
        "To test with real traffic: connect a VPN client and generate > 1 MB of traffic "
        "through the tunnel. Observe the same transition measured above, but driven by "
        "real Xray stats rather than a DB injection."
    )
    client_required(
        "Existing tunnel at quota hit: survives until natural TCP close "
        "(same as disable — RemoveUser does not kill goroutines)."
    )
    client_required(
        "Reconnect after limit: rejected immediately. "
        "Calling reset usage (POST /api/user/{username}/reset) restores access."
    )

    r.measure("enforcement_mechanism", "background job review() every 10 s")
    r.measure("quota_pushed_to_xray", "No — Xray has no quota concept")
    r.measure("data_limit_zero_meaning", "0 = unlimited (not zero bytes)")

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
