"""
test_rate_limit.py — Unit tests for Phase 3.3 Rate Limiting & Abuse Protection.

Tests:
  - Sliding Window Log algorithm, ported to run against BOTH MemoryRateLimitBackend and
    RedisRateLimitBackend (Finding H-3) via a parametrized `backend` fixture. The Redis
    backend is tested against an in-memory `fakeredis` simulator so these tests require no
    real Redis server.
  - RateLimiter check and key derivation (IP vs account ID)
  - Fail-open resilience (backend failure returns unlimited result)
  - Observability metrics incrementing on hits/blocks/errors
  - Zero-secret logging in RateLimiter
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from app.observability.metrics import metrics_registry
from app.rate_limit.backend import (
    MemoryRateLimitBackend,
    RateLimitBackend,
    RedisRateLimitBackend,
)
from app.rate_limit.exceptions import RateLimitExceeded
from app.rate_limit.limiter import RateLimiter
from fastapi import Request

fakeredis = pytest.importorskip(
    "fakeredis", reason="fakeredis is required to test RedisRateLimitBackend"
)
import fakeredis.aioredis  # noqa: E402


def make_dummy_request(
    path: str = "/api/auth/login", ip: str = "10.0.0.1", request_id: str = "req-123"
) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [],
        "client": (ip, 12345),
    }
    req = Request(scope)
    req.state.client_ip = ip
    req.state.request_id = request_id
    return req


@pytest_asyncio.fixture(params=["memory", "redis"])
async def backend(
    request: pytest.FixtureRequest,
) -> AsyncGenerator[RateLimitBackend, None]:
    """
    Parametrized fixture yielding both supported RateLimitBackend implementations
    (Finding H-3), so every test using it runs once against MemoryRateLimitBackend and
    once against RedisRateLimitBackend (backed by a fresh, isolated fakeredis instance).
    """
    if request.param == "memory":
        yield MemoryRateLimitBackend()
    else:
        fake_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        redis_backend = RedisRateLimitBackend(client=fake_client)
        yield redis_backend
        await redis_backend.aclose()


@pytest.mark.asyncio
async def test_backend_sliding_window_allow_and_block(backend: RateLimitBackend):
    """Verify the backend tracks requests and blocks when threshold is exceeded."""
    key = "test_ip_127.0.0.1"
    limit = 3
    window = 60

    # Request 1
    res1 = await backend.increment(key, window, limit)
    assert res1.allowed is True
    assert res1.limit == 3
    assert res1.remaining == 2

    # Request 2
    res2 = await backend.increment(key, window, limit)
    assert res2.allowed is True
    assert res2.remaining == 1

    # Request 3
    res3 = await backend.increment(key, window, limit)
    assert res3.allowed is True
    assert res3.remaining == 0

    # Request 4 - Should be blocked
    res4 = await backend.increment(key, window, limit)
    assert res4.allowed is False
    assert res4.remaining == 0
    assert res4.retry_after > 0
    assert res4.retry_after <= window


@pytest.mark.asyncio
async def test_backend_pruning_allows_after_window_expires(backend: RateLimitBackend):
    """Verify old timestamps are pruned so requests are allowed again after the window passes."""
    key = "test_pruning_key"
    limit = 2
    window = 1  # 1 second window for fast testing

    await backend.increment(key, window, limit)
    await backend.increment(key, window, limit)

    # Currently blocked
    res_blocked = await backend.increment(key, window, limit)
    assert res_blocked.allowed is False

    # Wait for window to pass
    await asyncio.sleep(1.1)

    # Should be pruned and allowed again
    res_allowed = await backend.increment(key, window, limit)
    assert res_allowed.allowed is True
    assert res_allowed.remaining == 1


@pytest.mark.asyncio
async def test_backend_denied_request_does_not_occupy_window_slot(
    backend: RateLimitBackend,
):
    """
    A denied request must not permanently consume a sliding-window slot: after being denied,
    the count of tracked entries for the key must remain exactly at max_requests (not
    max_requests + 1), so the very next allowed request has correct remaining/limit math.
    """
    key = "test_denied_slot_key"
    limit = 1
    window = 60

    res1 = await backend.increment(key, window, limit)
    assert res1.allowed is True

    res2 = await backend.increment(key, window, limit)
    assert res2.allowed is False

    res3 = await backend.increment(key, window, limit)
    assert res3.allowed is False
    # If the denied request in res2 had incorrectly occupied a slot, retry_after/reset would
    # drift upward across repeated denials. Confirm they stay anchored to the original entry.
    assert res3.reset == res2.reset


@pytest.mark.asyncio
async def test_backend_reset_and_clear(backend: RateLimitBackend):
    """Verify reset() removes a specific key and clear() removes all keys."""
    await backend.increment("key1", 60, 5)
    await backend.increment("key2", 60, 5)
    assert await backend.get_active_key_count() == 2

    await backend.reset("key1")
    assert await backend.get_active_key_count() == 1

    await backend.clear()
    assert await backend.get_active_key_count() == 0


@pytest.mark.asyncio
async def test_rate_limiter_fail_open_on_backend_error(backend: RateLimitBackend):
    """Verify RateLimiter fails open (returns unlimited) if the storage backend raises an exception."""
    limiter = RateLimiter(backend)

    # Patch backend.increment to raise an error
    with patch.object(backend, "increment", new_callable=AsyncMock) as mock_inc:
        mock_inc.side_effect = RuntimeError("Simulated Redis connection timeout")

        req = make_dummy_request(ip="192.168.1.100")
        result = await limiter.check(req, "login")

        # Must fail open
        assert result.allowed is True
        assert result.limit == 999999
        assert result.remaining == 999999

        # Verify backend error metric was incremented
        summary = metrics_registry.get_summary()
        assert summary.get("rate_limit_backend_errors", 0) >= 1.0


@pytest.mark.asyncio
async def test_rate_limiter_exceeded_raises_exception(backend: RateLimitBackend):
    """Verify RateLimiter.enforce() raises RateLimitExceeded when rule threshold is breached."""
    limiter = RateLimiter(backend)
    req = make_dummy_request(ip="10.0.0.1")

    # Login limit is 10/minute by default in config
    for _ in range(10):
        res = await limiter.enforce(req, "login")
        assert res.allowed is True

    # 11th request must raise RateLimitExceeded
    with pytest.raises(RateLimitExceeded) as exc_info:
        await limiter.enforce(req, "login")

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["X-RateLimit-Limit"] == "10"
    assert exc_info.value.headers["X-RateLimit-Remaining"] == "0"
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_rate_limiter_zero_secret_logging(backend: RateLimitBackend, caplog):
    """Verify rate limit logs hash IP addresses and never log raw sensitive credentials."""
    limiter = RateLimiter(backend)
    req = make_dummy_request(ip="203.0.113.50", request_id="req-123")

    with caplog.at_level("WARNING"):
        # Exceed limit
        for _ in range(11):
            try:
                await limiter.enforce(req, "login")
            except RateLimitExceeded:
                pass

    warnings = [
        r.message
        for r in caplog.records
        if "Abuse protection rate limit exceeded" in r.message
    ]
    assert len(warnings) > 0
    # Ensure raw IP 203.0.113.50 is NOT in log, but ip_hash is present
    assert "203.0.113.50" not in warnings[0]
    assert "ip_hash=" in warnings[0]
