#!/usr/bin/env python3
"""
Test 08 — Full Stack Persistence
Phase 0.3: Marzban Runtime Validation

Verifies that users, inbounds, the REALITY private key, and admin credentials
all survive a complete `docker compose down` + `docker compose up -d` cycle.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import (
    ADMIN_PASS,
    ADMIN_USER,
    DB_PATH,
    LAB_ROOT,
    CleanupGuard,
    MarzbanClient,
    Result,
    docker_compose,
    note,
    row,
    section,
    step,
    wait_for_marzban,
    warn,
)

TEST_USER = "poc_t08"

# Known lab constant — the REALITY private key must survive the restart unchanged.
KNOWN_REALITY_KEY = "WFnBJDEA7lwfIpT3SsCQyhhfK6d-8AzRLnVSlgBFbXY"


def _find_key(obj: object, key: str) -> object:
    """Recursively return the first value mapped to *key* in a nested dict/list."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_key(item, key)
            if found is not None:
                return found
    return None


def _inbound_tag_exists(inbounds: object, tag: str) -> bool:
    if not isinstance(inbounds, dict):
        return False
    for _proto, ibs in inbounds.items():
        if isinstance(ibs, list):
            for ib in ibs:
                if isinstance(ib, dict) and ib.get("tag") == tag:
                    return True
    return False


def run() -> bool:
    r = Result("Test 08 — Full Stack Persistence")

    # ── Step 1: Create test user, record UUID ────────────────────────────────
    section("Pre-restart state capture")
    step("Connecting to Marzban")
    c = MarzbanClient()

    step(f"Creating test user {TEST_USER} (VLESS TCP REALITY)")
    status, user_body = c.create_user(TEST_USER)
    if not r.check(f"User {TEST_USER} created", status == 200, f"HTTP {status}"):
        return r.summary()

    pre_uuid = ""
    if isinstance(user_body, dict):
        vless = user_body.get("proxies", {}).get("vless", {})
        pre_uuid = vless.get("id", "") if isinstance(vless, dict) else ""
    note(f"Recorded user UUID : {pre_uuid}")

    # ── Step 2: Record REALITY privateKey ────────────────────────────────────
    step("GET /api/inbounds — recording REALITY privateKey")
    s, inbounds = c.get_inbounds()
    pre_reality_key = (_find_key(inbounds, "privateKey") or "") if s == 200 else ""
    if not pre_reality_key:
        warn(
            "privateKey not found in /api/inbounds response — falling back to /api/core/config"
        )
        s2, core_cfg = c.get("/api/core/config")
        pre_reality_key = (_find_key(core_cfg, "privateKey") or "") if s2 == 200 else ""
    note(
        f"Recorded privateKey: {pre_reality_key[:20]}…"
        if pre_reality_key
        else "NOT FOUND — assertions will fail"
    )

    # ── Step 3: Record admin username ────────────────────────────────────────
    step("GET /api/admin — recording admin username")
    s, admin_data = c.get_admin()
    pre_admin_user = (
        admin_data.get("username", "")
        if s == 200 and isinstance(admin_data, dict)
        else ""
    )
    note(f"Recorded admin username: {pre_admin_user}")

    # ── Step 4: Pre-shutdown state summary ───────────────────────────────────
    section("Pre-shutdown state summary")
    row("test_user", TEST_USER)
    row("user_uuid (first 8)", (pre_uuid[:8] + "…") if pre_uuid else "NOT FOUND")
    row(
        "reality_key (first 20)",
        (pre_reality_key[:20] + "…") if pre_reality_key else "NOT FOUND",
    )
    row("admin_username", pre_admin_user)

    with CleanupGuard(c, TEST_USER) as guard:
        # ── Step 5: docker compose down ───────────────────────────────────────
        section("Container lifecycle — DOWN")
        step("docker compose down")
        shutdown_start = time.time()
        r_down = docker_compose("down")
        shutdown_duration_s = round(time.time() - shutdown_start, 1)
        r.check(
            "docker compose down succeeded",
            r_down.returncode == 0,
            f"rc={r_down.returncode}",
        )
        r.measure("shutdown_duration_s", shutdown_duration_s)

        # ── Step 6: docker compose up + wait for Marzban ──────────────────────
        section("Container lifecycle — UP")
        step("docker compose up -d")
        r_up = docker_compose("up", "-d")
        r.check(
            "docker compose up -d succeeded",
            r_up.returncode == 0,
            f"rc={r_up.returncode}",
        )

        step("Waiting for Marzban API to become ready (timeout 120s)…")
        startup_duration_s = wait_for_marzban(timeout=120)
        note(f"Marzban ready after {startup_duration_s:.1f}s")
        r.measure("startup_duration_s", round(startup_duration_s, 1))

        # ── Step 7: Reconnect ─────────────────────────────────────────────────
        section("Reconnect")
        step("Creating fresh MarzbanClient (re-authentication after restart)")
        c = MarzbanClient()
        guard._client = c  # redirect cleanup guard to the new authenticated client

        # ── Step 8: Post-restart assertions ───────────────────────────────────
        section("Post-restart assertions")

        # a) user survival + UUID unchanged
        step(f"a) GET /api/user/{TEST_USER}")
        s, user_data = c.get_user(TEST_USER)
        user_survived = s == 200
        post_uuid = ""
        if user_survived and isinstance(user_data, dict):
            vless = user_data.get("proxies", {}).get("vless", {})
            post_uuid = vless.get("id", "") if isinstance(vless, dict) else ""
        uuid_unchanged = bool(pre_uuid and pre_uuid == post_uuid)
        r.check(f"User {TEST_USER} still exists", user_survived, f"HTTP {s}")
        r.check(
            "User UUID unchanged after restart",
            uuid_unchanged,
            (post_uuid[:8] + "…") if post_uuid else "no uuid returned",
        )
        r.measure("user_survived", user_survived)
        r.measure("uuid_unchanged", uuid_unchanged)

        # b) inbound survival
        step("b) GET /api/inbounds")
        s, inbounds = c.get_inbounds()
        inbound_survived = (
            _inbound_tag_exists(inbounds, "VLESS TCP REALITY") if s == 200 else False
        )
        r.check("'VLESS TCP REALITY' inbound still present", inbound_survived)

        # c) REALITY privateKey unchanged
        step("c) GET /api/core/config — REALITY privateKey")
        s, core_cfg = c.get("/api/core/config")
        post_reality_key = (_find_key(core_cfg, "privateKey") or "") if s == 200 else ""
        reality_key_unchanged = bool(
            pre_reality_key and pre_reality_key == post_reality_key
        )
        r.check(
            "REALITY privateKey unchanged after full restart",
            reality_key_unchanged,
            "match"
            if reality_key_unchanged
            else f"expected {pre_reality_key[:20]}… got {post_reality_key[:20]}…",
        )
        r.check(
            "REALITY privateKey matches known lab constant",
            post_reality_key == KNOWN_REALITY_KEY,
            f"got: {post_reality_key[:20]}…" if post_reality_key else "NOT FOUND",
        )
        r.measure("reality_key_unchanged", reality_key_unchanged)

        # d) admin username unchanged
        step("d) GET /api/admin")
        s, admin_data = c.get_admin()
        post_admin_user = (
            admin_data.get("username", "")
            if s == 200 and isinstance(admin_data, dict)
            else ""
        )
        admin_survived = bool(pre_admin_user and post_admin_user == pre_admin_user)
        r.check(
            f"Admin username still '{pre_admin_user}'",
            admin_survived,
            f"got '{post_admin_user}'",
        )
        r.measure("admin_survived", admin_survived)

        # e) DB file exists on host filesystem
        step("e) Check DB file exists on host")
        db_exists = DB_PATH.exists()
        r.check(
            f"DB file exists at data/marzban/db.sqlite3",
            db_exists,
            str(DB_PATH) if not db_exists else "present",
        )
        r.measure("db_exists", db_exists)

    # Cleanup handled by CleanupGuard.__exit__ using the re-authenticated client
    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
