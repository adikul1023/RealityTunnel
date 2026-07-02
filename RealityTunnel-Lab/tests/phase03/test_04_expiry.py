#!/usr/bin/env python3
"""
Test 04 — Expiry Enforcement
Phase 0.3: Marzban Runtime Validation

What this tests:
  - Setting expire to a past timestamp via PUT is enforced inline (same API call).
  - Setting expire to a future timestamp: the background job (review, every 10 s)
    detects expiry and calls gRPC RemoveUser. This test measures the actual lag.
  - What happens to Xray and the subscription URL after expiry.

What it requires:
  - Marzban running in Docker.
  - No VPN client needed for server-side assertions.
  - CLIENT REQUIRED section documents the tunnel behavior.

Key facts encoded:
  - review() job runs every JOB_REVIEW_USERS_INTERVAL seconds (default 10).
  - Expiry check: expire <= now_ts (Unix timestamp).
  - Expiry via PUT (past value) is immediate — Marzban recalculates status inline.
  - Natural expiry (time passes) is background-job-driven: worst-case ~10 s lag.
  - RemoveUser does NOT terminate existing sessions.
"""

import datetime
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
    step,
    warn,
)

TEST_USER_PAST = "poc_t04a"
TEST_USER_FUTURE = "poc_t04b"
# How far ahead to set the future expiry (seconds). Must be > job interval (10 s).
FUTURE_OFFSET_S = 45
# Max time to wait for the background job to enforce expiry.
WATCH_TIMEOUT_S = 90
POLL_INTERVAL_S = 2


def run() -> bool:
    r = Result("Test 04 — Expiry Enforcement")
    c = MarzbanClient()

    # ── Part A: immediate enforcement via PUT with past expire ─────────────

    section("PART A — Inline enforcement: expire set to past via PUT")

    step("Create poc_t04a")
    status, body = c.create_user(TEST_USER_PAST)
    r.check("create_user HTTP 200", status == 200)
    initial_status = body.get("status") if isinstance(body, dict) else None
    r.check("initial status == active", initial_status == "active")

    with CleanupGuard(c, TEST_USER_PAST):
        step("PUT expire=1 (Unix epoch — definitely past)")
        with LogWindow() as lw:
            t0 = time.time()
            status, body = c.modify_user(TEST_USER_PAST, expire=1)
            elapsed = time.time() - t0

        r.check("PUT HTTP 200", status == 200)
        new_status = body.get("status") if isinstance(body, dict) else "?"
        r.check("status immediately == expired", new_status == "expired")
        r.check(
            "expire field == 1",
            body.get("expire") == 1 if isinstance(body, dict) else False,
        )
        r.measure("inline_enforcement_ms", f"{elapsed * 1000:.0f} ms")

        step("Verify logs — status transition")
        lw.print_new()
        r.check(
            "log: status changed to UserStatus.expired",
            lw.contains("UserStatus.expired"),
        )
        r.check(
            "log: no Xray core restart",
            not lw.contains("Restarting Xray core"),
        )

        step("GET user — verify persisted state")
        status, body = c.get_user(TEST_USER_PAST)
        r.check("GET HTTP 200", status == 200)
        r.check(
            "status == expired after GET",
            body.get("status") == "expired" if isinstance(body, dict) else False,
        )

        step("Verify subscription URL still serves content for expired user")
        sub_url = body.get("subscription_url", "") if isinstance(body, dict) else ""
        if sub_url:
            sub_status, _ = c.get_sub(sub_url)
            r.check(
                "subscription URL response for expired user",
                sub_status == 200,
                f"HTTP {sub_status} (sub URL does not 4xx on expiry)",
            )
            r.measure(
                "sub_url_on_expired_user", f"HTTP {sub_status} (still serves link)"
            )
        else:
            note("No subscription_url in response — skipping sub URL check")

    # ── Part B: natural expiry — background job timing ─────────────────────

    section("PART B — Natural expiry: background job enforcement timing")

    step(f"Create poc_t04b with expire = now + {FUTURE_OFFSET_S}s")
    expire_ts = int(time.time()) + FUTURE_OFFSET_S
    expires_at = datetime.datetime.utcfromtimestamp(expire_ts).strftime("%H:%M:%S UTC")
    note(f"Expiry scheduled at: {expires_at}")
    status, body = c.create_user(TEST_USER_FUTURE, expire=expire_ts)
    r.check("create_user HTTP 200", status == 200)
    r.check(
        "initial status == active",
        body.get("status") == "active" if isinstance(body, dict) else False,
    )

    with CleanupGuard(c, TEST_USER_FUTURE):
        step(f"Waiting for natural expiry (up to {WATCH_TIMEOUT_S}s)...")
        note("Polling GET /api/user every 2s. Background job runs every ~10s.")

        detected_at = None
        transition_lag = None
        poll_count = 0

        deadline = time.time() + WATCH_TIMEOUT_S
        while time.time() < deadline:
            _, u = c.get_user(TEST_USER_FUTURE)
            poll_count += 1
            if isinstance(u, dict) and u.get("status") == "expired":
                detected_at = time.time()
                transition_lag = detected_at - expire_ts
                break
            remaining = expire_ts - time.time()
            if remaining > 0:
                print(
                    f"\r     polling... (expire in {remaining:.0f}s, polls: {poll_count})",
                    end="",
                    flush=True,
                )
            else:
                print(
                    f"\r     polling... (past expiry by {-remaining:.0f}s, polls: {poll_count})",
                    end="",
                    flush=True,
                )
            time.sleep(POLL_INTERVAL_S)

        print()  # newline after \r

        if detected_at is None:
            fail(f"Status did not transition to expired within {WATCH_TIMEOUT_S}s")
            r.failed += 1
            r.measure("natural_expiry_lag_s", "TIMEOUT — not enforced within window")
        else:
            ok(
                f"Status transitioned to expired after {transition_lag:.1f}s past expiry timestamp"
            )
            r.passed += 1
            r.measure("natural_expiry_lag_s", f"{transition_lag:.1f}s after expire_ts")
            r.measure("polls_until_detection", poll_count)
            r.check(
                "background job enforced expiry within 30s of timestamp",
                transition_lag <= 30,
                f"actual lag: {transition_lag:.1f}s",
            )

        step("Final GET — confirm state")
        _, final = c.get_user(TEST_USER_FUTURE)
        final_status = final.get("status") if isinstance(final, dict) else "?"
        r.check("final status == expired", final_status == "expired", final_status)

    # ── Session behavior note ──────────────────────────────────────────────

    section("CLIENT REQUIRED — Active Session Behavior")
    client_required("Connect a VPN client using poc_t04b's config before expiry.")
    client_required(
        "Existing TCP session: survives expiry event indefinitely "
        "(Xray RemoveUser does not close goroutines). "
        "No tunnel drop at the moment of enforcement."
    )
    client_required(
        "After natural disconnect, reconnect attempt: rejected immediately "
        "(UUID no longer registered in Xray handler)."
    )
    client_required(
        "Dashboard state: user appears as 'expired'."
        " Subscription URL still returns HTTP 200 with the VLESS link."
    )

    r.measure("background_job_interval", "10 s (JOB_REVIEW_USERS_INTERVAL default)")
    r.measure(
        "inline_expiry_set_to_past",
        "Immediate — status recalculated in same PUT request",
    )
    r.measure(
        "natural_expiry_lag", "Measured above — up to ~10 s after expire timestamp"
    )

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
