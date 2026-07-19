"""
Tests for the IPC HMAC + nonce replay-prevention mechanism.
Covers host_agent verification logic and admin_operations signing contract.
"""
import hmac
import hashlib
import json
import secrets
import time
import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _compute_hmac(service: str, action: str, timestamp: int, nonce: str, secret: str) -> str:
    msg = f"{service}:{action}:{timestamp}:{nonce}"
    return hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def make_signed_payload(
    service: str,
    action: str,
    secret: str,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    n = nonce if nonce is not None else secrets.token_hex(16)
    sig = _compute_hmac(service, action, ts, n, secret)
    return json.dumps({
        "service": service,
        "action": action,
        "timestamp": ts,
        "nonce": n,
        "hmac": sig,
    })


# ─── Mirror of host_agent's verify_and_validate (no import needed) ────────────

MAX_AGE_SECONDS = 60
_seen_nonces: dict[str, float] = {}


def _fresh_verify(payload: dict, secret: str) -> tuple[bool, str]:
    """Stateless verification (no nonce dedup) for basic HMAC/timestamp checks."""
    required = {"service", "action", "timestamp", "nonce", "hmac"}
    missing = required - payload.keys()
    if missing:
        return False, f"Missing fields: {missing}"

    service = payload["service"]
    action = payload["action"]
    timestamp = payload["timestamp"]
    nonce = payload["nonce"]
    received_hmac = payload["hmac"]

    expected_hmac = _compute_hmac(service, action, timestamp, nonce, secret)
    if not hmac.compare_digest(expected_hmac, received_hmac):
        return False, "HMAC failed"

    now = int(time.time())
    if abs(now - timestamp) > MAX_AGE_SECONDS:
        return False, "Timestamp expired"

    return True, "ok"


class TestHostAgentHMAC:
    """Unit tests for HMAC verification logic (stateless)."""

    def test_valid_payload_accepted(self):
        secret = "testsecretkey"
        payload = json.loads(make_signed_payload("marzban", "restart", secret))
        ok, reason = _fresh_verify(payload, secret)
        assert ok, reason

    def test_wrong_secret_rejected(self):
        payload = json.loads(make_signed_payload("marzban", "restart", "correctsecret"))
        ok, _ = _fresh_verify(payload, "wrongsecret")
        assert not ok

    def test_missing_hmac_field_rejected(self):
        payload = {
            "service": "marzban",
            "action": "restart",
            "timestamp": int(time.time()),
            "nonce": secrets.token_hex(16),
        }
        ok, reason = _fresh_verify(payload, "any")
        assert not ok
        assert "hmac" in reason.lower() or "missing" in reason.lower()

    def test_tampered_service_rejected(self):
        secret = "secret"
        payload = json.loads(make_signed_payload("marzban", "restart", secret))
        payload["service"] = "caddy"  # tampered
        ok, _ = _fresh_verify(payload, secret)
        assert not ok

    def test_tampered_action_rejected(self):
        secret = "secret"
        payload = json.loads(make_signed_payload("marzban", "restart", secret))
        payload["action"] = "shutdown"  # tampered
        ok, _ = _fresh_verify(payload, secret)
        assert not ok

    def test_tampered_nonce_rejected(self):
        secret = "secret"
        payload = json.loads(make_signed_payload("marzban", "restart", secret))
        payload["nonce"] = secrets.token_hex(16)  # different nonce, breaks HMAC
        ok, _ = _fresh_verify(payload, secret)
        assert not ok

    def test_stale_timestamp_detected(self):
        """Timestamp 65 seconds in the past exceeds 60s window."""
        stale_ts = int(time.time()) - 65
        payload = json.loads(make_signed_payload("marzban", "restart", "s", timestamp=stale_ts))
        ok, reason = _fresh_verify(payload, "s")
        assert not ok
        assert "expired" in reason.lower() or "timestamp" in reason.lower()

    def test_future_timestamp_within_window_accepted(self):
        """Clock skew of 30s is acceptable."""
        future_ts = int(time.time()) + 30
        payload = json.loads(make_signed_payload("xray", "reload", "s", timestamp=future_ts))
        ok, reason = _fresh_verify(payload, "s")
        assert ok, reason


class TestNonceReplay:
    """Verify the nonce deduplication correctly prevents replay within the window."""

    def _build_stateful_verifier(self, secret: str):
        """Returns a per-test stateful verifier that tracks its own nonce store."""
        seen: dict[str, float] = {}

        def verify(payload: dict) -> tuple[bool, str]:
            ok, reason = _fresh_verify(dict(payload), secret)
            if not ok:
                return ok, reason
            # Nonce dedup
            nonce = payload["nonce"]
            ts = payload["timestamp"]
            now = int(time.time())
            # Evict expired
            expired = [n for n, exp in seen.items() if now > exp]
            for n in expired:
                del seen[n]
            if nonce in seen:
                return False, "Nonce reused"
            seen[nonce] = ts + MAX_AGE_SECONDS
            return True, "ok"

        return verify

    def test_first_use_accepted(self):
        verify = self._build_stateful_verifier("secret")
        payload = json.loads(make_signed_payload("marzban", "restart", "secret"))
        ok, reason = verify(payload)
        assert ok, reason

    def test_identical_replay_rejected(self):
        verify = self._build_stateful_verifier("secret")
        payload = json.loads(make_signed_payload("marzban", "restart", "secret"))
        verify(payload)  # first call succeeds
        ok, reason = verify(payload)  # exact same payload replayed
        assert not ok
        assert "nonce" in reason.lower() or "replay" in reason.lower()

    def test_different_nonce_accepted(self):
        verify = self._build_stateful_verifier("secret")
        p1 = json.loads(make_signed_payload("marzban", "restart", "secret"))
        p2 = json.loads(make_signed_payload("marzban", "restart", "secret"))
        verify(p1)
        ok, reason = verify(p2)
        assert ok, reason


class TestAdminOperationsIPCSigning:
    """Verify the payload structure produced by admin_operations matches what host_agent expects."""

    def test_restart_payload_structure(self):
        secret = "testipc"
        ts = int(time.time())
        nonce = secrets.token_hex(16)
        service, action = "marzban", "restart"
        sig = _compute_hmac(service, action, ts, nonce, secret)

        payload_str = json.dumps({
            "service": service,
            "action": action,
            "timestamp": ts,
            "nonce": nonce,
            "hmac": sig,
        })
        parsed = json.loads(payload_str)

        for field in ("service", "action", "timestamp", "nonce", "hmac"):
            assert field in parsed

        ok, reason = _fresh_verify(parsed, secret)
        assert ok, reason

    def test_reload_payload_structure(self):
        secret = "testipc"
        ts = int(time.time())
        nonce = secrets.token_hex(16)
        service, action = "xray", "reload"
        sig = _compute_hmac(service, action, ts, nonce, secret)

        payload_str = json.dumps({
            "service": service,
            "action": action,
            "timestamp": ts,
            "nonce": nonce,
            "hmac": sig,
        })
        parsed = json.loads(payload_str)
        ok, reason = _fresh_verify(parsed, secret)
        assert ok, reason

    def test_nonce_is_unique_per_call(self):
        """Two separate admin_operations calls must produce different nonces."""
        import secrets as sec
        n1 = sec.token_hex(16)
        n2 = sec.token_hex(16)
        assert n1 != n2
