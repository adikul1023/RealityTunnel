"""
tests/core/test_rate_limit_storage.py — Regression tests for Finding H-3 backend selection.

app.rate_limit.storage.get_rate_limit_backend() previously always returned
MemoryRateLimitBackend regardless of configuration. It now selects the backend based on
settings.rate_limit_backend ("memory" | "redis").

IMPORTANT: get_rate_limit_backend() is @lru_cache'd as a process-wide singleton, and the
live RateLimiter singleton (app.rate_limit.limiter.get_rate_limiter()) independently caches
whatever backend instance it first resolves. tests/conftest.py's autouse cleanup fixture
calls get_rate_limit_backend().clear() before every test, relying on that call returning
the SAME instance the running application actually uses. Clearing/repopulating this cache
from a test (e.g. via get_rate_limit_backend.cache_clear()) would desynchronize it from the
RateLimiter singleton's already-cached backend reference, silently breaking rate-limit
isolation between tests for the rest of the suite. To avoid this, these tests exercise the
backend-selection logic via the underlying undecorated function
(get_rate_limit_backend.__wrapped__), which never touches the shared cache at all.
"""

from __future__ import annotations

from unittest.mock import patch

from app.config import settings
from app.rate_limit.backend import MemoryRateLimitBackend, RedisRateLimitBackend
from app.rate_limit.storage import get_rate_limit_backend


def _select_backend():
    """Invoke the backend-selection logic directly, bypassing the shared lru_cache."""
    return get_rate_limit_backend.__wrapped__()


def test_get_rate_limit_backend_defaults_to_memory():
    """With rate_limit_backend='memory' (the default), the memory backend is selected."""
    with patch.object(settings, "rate_limit_backend", "memory"):
        backend = _select_backend()
        assert isinstance(backend, MemoryRateLimitBackend)


def test_get_rate_limit_backend_selects_redis_when_configured():
    """
    With rate_limit_backend='redis', a RedisRateLimitBackend is selected. redis.asyncio
    connections are lazily established on first command, so constructing the client here
    does not require (and must not require) a reachable Redis server.
    """
    with patch.object(settings, "rate_limit_backend", "redis"):
        backend = _select_backend()
        assert isinstance(backend, RedisRateLimitBackend)


def test_get_rate_limit_backend_is_a_singleton_per_process():
    """
    The public, cached factory returns the exact same instance on repeated calls within a
    process. This reads the real shared singleton (as every other code path does) without
    clearing or repopulating its cache.
    """
    first = get_rate_limit_backend()
    second = get_rate_limit_backend()
    assert first is second
