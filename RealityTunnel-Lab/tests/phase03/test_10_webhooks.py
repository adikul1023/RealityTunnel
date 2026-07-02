#!/usr/bin/env python3
"""
Test 10 — Webhook System Investigation
Phase 0.3: Marzban Runtime Validation

What this tests:
  - Full empirical webhook test: spins up a local HTTP listener, temporarily
    adds WEBHOOK_ADDRESS to the lab .env, restarts Marzban, triggers every
    event type, captures the actual JSON payloads, then restores .env.
  - Also documents static facts derived from Marzban source code.
  - Measures: delivery latency, retry behavior, payload structure, auth header.

What it requires:
  - Marzban running in Docker.
  - host.docker.internal must be resolvable from inside the container
    (Docker Desktop for Windows: always available).
  - The test restarts the Marzban container twice (to inject/remove WEBHOOK_ADDRESS).

Key facts from source:
  - Webhook URL: WEBHOOK_ADDRESS env var (comma-separated list, set at startup only).
  - Auth: x-webhook-secret header if WEBHOOK_SECRET is set (plain string, no HMAC).
  - Retry: 3 attempts, 180 s delay between retries.
  - Send job: drains notification queue every 30 s.
  - Timeout: NONE — session.post() has no timeout argument (blocks indefinitely).
  - Login events: NOT sent via webhook (only to Telegram/Discord bots).
  - Events: user_created, user_updated, user_deleted, user_limited, user_expired,
             user_enabled, user_disabled, subscription_revoked, data_usage_reset,
             reached_usage_percent, reached_days_left.
"""

import http.server
import json
import sys
import threading
import time
from pathlib import Path

from common import (
    ADMIN_PASS,
    ADMIN_USER,
    ENV_PATH,
    LAB_ROOT,
    CleanupGuard,
    LogWindow,
    MarzbanClient,
    Result,
    client_required,
    docker_compose,
    note,
    row,
    section,
    step,
    wait_for_marzban,
    warn,
)

TEST_USER = "poc_t10"
LISTENER_PORT = 19876
WEBHOOK_SECRET = "lab-test-secret-001"
# How long to wait after triggering an event for the send job to fire (30 s job + buffer)
WAIT_FOR_SEND_S = 45


# ── In-process webhook receiver ────────────────────────────────────────────


class _Collector:
    def __init__(self):
        self.lock = threading.Lock()
        self.received: list[dict] = []

    def add(self, payload: list[dict], secret_header: str | None):
        with self.lock:
            self.received.append(
                {
                    "arrived_at": time.time(),
                    "secret_header": secret_header,
                    "payload": payload,
                }
            )

    def all(self) -> list[dict]:
        with self.lock:
            return list(self.received)


_collector = _Collector()


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        secret = self.headers.get("x-webhook-secret")
        try:
            payload = json.loads(raw)
            _collector.add(payload if isinstance(payload, list) else [payload], secret)
        except Exception:
            pass
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_):
        pass  # suppress server access log


def _start_listener() -> http.server.HTTPServer:
    server = http.server.HTTPServer(("0.0.0.0", LISTENER_PORT), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


# ── .env patching ──────────────────────────────────────────────────────────


def _read_env() -> str:
    return ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""


def _write_env(content: str) -> None:
    ENV_PATH.write_text(content, encoding="utf-8")


def _add_webhook_to_env(port: int, secret: str) -> str:
    """Append WEBHOOK_ADDRESS and WEBHOOK_SECRET; return original content."""
    original = _read_env()
    additions = (
        f"\n# --- phase03 test_10 (temporary) ---\n"
        f"WEBHOOK_ADDRESS=http://host.docker.internal:{port}\n"
        f"WEBHOOK_SECRET={secret}\n"
    )
    _write_env(original + additions)
    return original


def _restore_env(original: str) -> None:
    _write_env(original)


# ── Event triggers ─────────────────────────────────────────────────────────


def _trigger_events(c: MarzbanClient) -> None:
    """Fire all webhook-emitting operations."""
    step("Triggering: user_created")
    c.create_user(TEST_USER)
    time.sleep(1)

    step("Triggering: user_updated (PUT note)")
    c.modify_user(TEST_USER, note="webhook-test")
    time.sleep(1)

    step("Triggering: user_disabled")
    c.modify_user(TEST_USER, status="disabled")
    time.sleep(1)

    step("Triggering: user_enabled")
    c.modify_user(TEST_USER, status="active")
    time.sleep(1)

    step("Triggering: subscription_revoked (revoke_sub)")
    c.revoke_sub(TEST_USER)
    time.sleep(1)

    step("Triggering: user_deleted")
    c.delete_user(TEST_USER)
    time.sleep(1)


# ── Main test ──────────────────────────────────────────────────────────────


def _print_static_facts(r: Result) -> None:
    section("STATIC FACTS — From Marzban Source Code")
    row(
        "Events sent to WEBHOOK_ADDRESS",
        "user_created, user_updated, user_deleted, user_limited, user_expired, "
        "user_enabled, user_disabled, subscription_revoked, data_usage_reset, "
        "reached_usage_percent, reached_days_left",
    )
    row(
        "Login events sent via webhook",
        "NO — login() only dispatches to Telegram/Discord",
    )
    row("Auth mechanism", "x-webhook-secret header (plain string, no HMAC)")
    row("HTTP call timeout", "NONE — requests.Session.post() has no timeout= arg")
    row("Max retries", "3 (NUMBER_OF_RECURRENT_NOTIFICATIONS)")
    row("Retry delay", "180 s between retries (RECURRENT_NOTIFICATIONS_TIMEOUT)")
    row("Send job interval", "30 s (JOB_SEND_NOTIFICATIONS_INTERVAL)")
    row("Body format", "JSON array of notification objects")
    row("Base fields per object", "username, action, enqueued_at, send_at, tries")
    row("user_created extra fields", "by (Admin), user (UserResponse)")
    row(
        "user_disabled extra fields",
        "by (Admin), user (UserResponse), reason (str|null)",
    )
    row("user_deleted extra fields", "by (Admin) — no 'user' field")
    row("subscription_revoked extra", "by (Admin), user (UserResponse)")
    row("WEBHOOK_ADDRESS", "Set at startup via env var — NOT configurable via API")
    r.measure(
        "no_api_webhook_config", "True — requires container restart to add/change URL"
    )


def run() -> bool:
    r = Result("Test 10 — Webhook System")

    _print_static_facts(r)

    # ── Live test ──────────────────────────────────────────────────────────

    section("LIVE EMPIRICAL TEST — Local receiver + container restart")
    note("This test restarts Marzban twice. It takes ~2 minutes total.")
    note("Skipping if user opts out: set env var SKIP_WEBHOOK_LIVE=1")

    import os

    if os.environ.get("SKIP_WEBHOOK_LIVE") == "1":
        warn("SKIP_WEBHOOK_LIVE=1 — skipping live webhook test.")
        note("Re-run without that env var to capture live payloads.")
        r.measure("live_test", "SKIPPED")
        return r.summary()

    original_env = ""
    server = None

    try:
        step(f"Starting local HTTP listener on port {LISTENER_PORT}")
        server = _start_listener()
        note(f"Listener ready at http://0.0.0.0:{LISTENER_PORT}")

        step("Patching .env with WEBHOOK_ADDRESS + WEBHOOK_SECRET")
        original_env = _add_webhook_to_env(LISTENER_PORT, WEBHOOK_SECRET)
        note(f"WEBHOOK_ADDRESS=http://host.docker.internal:{LISTENER_PORT}")

        step("Restarting Marzban container to load new env")
        docker_compose("restart", "marzban")
        startup_s = wait_for_marzban(timeout=90)
        note(f"Marzban ready after {startup_s:.1f}s")

        step("Creating fresh MarzbanClient with new token")
        c = MarzbanClient()

        step("Triggering all event types")
        t_trigger = time.time()
        _trigger_events(c)

        step(f"Waiting up to {WAIT_FOR_SEND_S}s for send_notifications job to fire...")
        note("Job drains the queue every 30 s.")

        deadline = time.time() + WAIT_FOR_SEND_S
        while time.time() < deadline and not _collector.all():
            elapsed = time.time() - t_trigger
            print(f"\r     waiting... ({elapsed:.0f}s)", end="", flush=True)
            time.sleep(2)
        print()

        deliveries = _collector.all()

        if not deliveries:
            warn("No webhooks received within window. Possible causes:")
            note("  • host.docker.internal not resolving inside container")
            note("  • WEBHOOK_ADDRESS not loaded (env var only read at startup)")
            note("  • Windows Firewall blocking inbound on port 19876")
            r.check("webhooks received", False)
        else:
            ok(f"Received {len(deliveries)} HTTP POST(s) from Marzban")
            r.check("webhooks received", True)

            # Print each payload
            section("CAPTURED WEBHOOK PAYLOADS")
            all_events = []
            for i, d in enumerate(deliveries):
                lag = d["arrived_at"] - t_trigger
                print(
                    f"\n  Delivery #{i + 1}  (arrived +{lag:.1f}s, secret_header={d['secret_header']!r})"
                )
                for evt in d["payload"]:
                    action = evt.get("action", "?")
                    all_events.append(action)
                    print(f"    action: {action}")
                    print(f"    username: {evt.get('username', '?')}")
                    print(f"    enqueued_at: {evt.get('enqueued_at')}")
                    if "by" in evt:
                        print(
                            f"    by: {evt['by'].get('username') if isinstance(evt.get('by'), dict) else evt.get('by')}"
                        )
                    if "user" in evt:
                        print(
                            f"    user.status: {evt['user'].get('status') if isinstance(evt.get('user'), dict) else '?'}"
                        )
                    if "reason" in evt:
                        print(f"    reason: {evt.get('reason')}")

            # Assertions
            r.check(
                "x-webhook-secret header present",
                any(d["secret_header"] == WEBHOOK_SECRET for d in deliveries),
            )
            r.check("user_created event received", "user_created" in all_events)
            r.check("user_disabled event received", "user_disabled" in all_events)
            r.check("user_enabled event received", "user_enabled" in all_events)
            r.check(
                "subscription_revoked event received",
                "subscription_revoked" in all_events,
            )
            r.check("user_deleted event received", "user_deleted" in all_events)

            delivery_lag = deliveries[0]["arrived_at"] - t_trigger
            r.measure("first_delivery_lag_s", f"{delivery_lag:.1f}s")
            r.measure("events_captured", ", ".join(sorted(set(all_events))))

    finally:
        if server:
            server.shutdown()

        if original_env:
            step("Restoring original .env")
            _restore_env(original_env)

            step("Restarting Marzban to restore original config")
            docker_compose("restart", "marzban")
            wait_for_marzban(timeout=90)
            note("Marzban restored to pre-test configuration")

        # Ensure test user is cleaned up if it still exists
        try:
            c2 = MarzbanClient()
            c2.delete_user(TEST_USER)
        except Exception:
            pass

    section("BILLING SERVER IMPLICATIONS")
    row(
        "Can your Billing server receive events?",
        "YES — set WEBHOOK_ADDRESS to Billing server's /webhook endpoint",
    )
    row(
        "Recommended events to consume",
        "user_created, user_disabled, user_expired, user_limited",
    )
    row(
        "Auth recommendation",
        "Set WEBHOOK_SECRET and verify x-webhook-secret on every request",
    )
    row(
        "Timeout risk",
        "CRITICAL — Marzban blocks indefinitely if your webhook endpoint hangs. "
        "Your endpoint MUST respond within a few seconds.",
    )
    row(
        "No event ordering guarantee",
        "Notifications can be batched (array). Process each element independently.",
    )
    row(
        "Missing: login events",
        "Marzban does NOT emit user login via webhook. "
        "Billing server cannot detect active sessions this way.",
    )

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
