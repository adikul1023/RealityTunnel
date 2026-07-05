"""
app/rate_limit/backend.py — Storage backend abstractions for rate limiting (Phase 3.3).
Provides RateLimitBackend interface, MemoryRateLimitBackend with Sliding Window Log, and
RedisRateLimitBackend (Finding H-3) for correctness across multiple horizontally-scaled
replicas and persistence across restarts.
"""

from __future__ import annotations

import asyncio
import math
import secrets
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Any

try:
    import redis.asyncio as aioredis
except (
    ImportError
):  # pragma: no cover - redis is a required production dependency (requirements.txt)
    aioredis = None  # type: ignore[assignment]

from app.rate_limit.exceptions import RateLimitBackendError
from app.rate_limit.models import RateLimitResult


class RateLimitBackend(ABC):
    """Abstract rate limit storage backend interface designed for Redis compatibility."""

    @abstractmethod
    async def increment(
        self, key: str, window_seconds: int, max_requests: int
    ) -> RateLimitResult:
        """Record a request for the given key and return the rate limit evaluation result."""
        pass

    @abstractmethod
    async def get(self, key: str) -> RateLimitResult:
        """Retrieve current rate limit status without incrementing count."""
        pass

    @abstractmethod
    async def reset(self, key: str) -> None:
        """Clear rate limit history for a key."""
        pass

    @abstractmethod
    async def ttl(self, key: str) -> int:
        """Return remaining seconds until the key's rate limit window expires (-1 if not found)."""
        pass

    @abstractmethod
    async def get_active_key_count(self) -> int:
        """Return the number of currently tracked rate limit keys (for observability metrics)."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all rate limit data (useful for test isolation)."""
        pass


class MemoryRateLimitBackend(RateLimitBackend):
    """
    In-memory rate limit storage backend implementing exact Sliding Window Log.
    Stores timestamps per key to eliminate fixed-window burst loopholes.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Stores key -> (deque of timestamps, max_requests, window_seconds)
        self._store: dict[str, tuple[deque[float], int, int]] = {}
        self._cleanup_counter = 0

    async def _prune_key_locked(
        self, key: str, now: float
    ) -> tuple[deque[float], int, int] | None:
        if key not in self._store:
            return None
        ts_deque, max_requests, window_seconds = self._store[key]
        cutoff = now - window_seconds
        while ts_deque and ts_deque[0] <= cutoff:
            ts_deque.popleft()
        if not ts_deque:
            del self._store[key]
            return None
        return ts_deque, max_requests, window_seconds

    async def _maybe_cleanup_locked(self, now: float) -> None:
        """Periodically prune stale keys to prevent memory leaks."""
        self._cleanup_counter += 1
        if self._cleanup_counter >= 100:
            self._cleanup_counter = 0
            stale_keys = []
            for k, (ts_deque, _, win_sec) in self._store.items():
                if not ts_deque or ts_deque[-1] <= (now - win_sec):
                    stale_keys.append(k)
            for k in stale_keys:
                self._store.pop(k, None)

    async def increment(
        self, key: str, window_seconds: int, max_requests: int
    ) -> RateLimitResult:
        if max_requests <= 0 or window_seconds <= 0:
            return RateLimitResult.unlimited()

        now = time.time()
        async with self._lock:
            await self._maybe_cleanup_locked(now)
            entry = await self._prune_key_locked(key, now)
            if entry is None:
                ts_deque: deque[float] = deque()
            else:
                ts_deque, _, _ = entry

            if len(ts_deque) >= max_requests:
                oldest = ts_deque[0]
                reset_at = int(oldest + window_seconds)
                retry_after = max(1, int(math.ceil((oldest + window_seconds) - now)))
                self._store[key] = (ts_deque, max_requests, window_seconds)
                return RateLimitResult(
                    allowed=False,
                    limit=max_requests,
                    remaining=0,
                    reset=reset_at,
                    retry_after=retry_after,
                )

            ts_deque.append(now)
            self._store[key] = (ts_deque, max_requests, window_seconds)
            remaining = max(0, max_requests - len(ts_deque))
            oldest = ts_deque[0]
            reset_at = int(oldest + window_seconds)
            return RateLimitResult(
                allowed=True,
                limit=max_requests,
                remaining=remaining,
                reset=reset_at,
                retry_after=0,
            )

    async def get(self, key: str) -> RateLimitResult:
        now = time.time()
        async with self._lock:
            entry = await self._prune_key_locked(key, now)
            if entry is None:
                return RateLimitResult.unlimited()
            ts_deque, max_requests, window_seconds = entry
            remaining = max(0, max_requests - len(ts_deque))
            oldest = ts_deque[0]
            reset_at = int(oldest + window_seconds)
            allowed = len(ts_deque) < max_requests
            retry_after = (
                max(1, int(math.ceil((oldest + window_seconds) - now)))
                if not allowed
                else 0
            )
            return RateLimitResult(
                allowed=allowed,
                limit=max_requests,
                remaining=remaining,
                reset=reset_at,
                retry_after=retry_after,
            )

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def ttl(self, key: str) -> int:
        now = time.time()
        async with self._lock:
            entry = await self._prune_key_locked(key, now)
            if entry is None:
                return -1
            ts_deque, _, window_seconds = entry
            oldest = ts_deque[0]
            return max(0, int(math.ceil((oldest + window_seconds) - now)))

    async def get_active_key_count(self) -> int:
        now = time.time()
        async with self._lock:
            await self._maybe_cleanup_locked(now)
            return len(self._store)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


class RedisRateLimitBackend(RateLimitBackend):
    """
    Redis-backed rate limit storage backend implementing exact Sliding Window Log via
    Redis Sorted Sets (Finding H-3).

    WHY REDIS INSTEAD OF IN-MEMORY:
    MemoryRateLimitBackend's state is process-local. Once the application is scaled
    horizontally (multiple worker processes or replicas behind a load balancer), each
    process tracks independent counters, silently multiplying the effective rate limit by
    the replica count, and every restart/redeploy resets all counters to zero. Redis
    provides a single shared, durable store so rate limits are enforced consistently across
    every replica and survive individual process restarts.

    WHY A SORTED SET PER KEY:
    Each rate-limited key (e.g. "ip:1.2.3.4:login") maps to a Redis Sorted Set whose members
    are unique per-request tokens and whose scores are the request timestamps. This mirrors
    MemoryRateLimitBackend's exact Sliding Window Log semantics (no fixed-window burst
    loopholes) rather than a coarser fixed-window counter.

    WHY A PIPELINE (MULTI/EXEC) INSTEAD OF A CHECK-THEN-ACT ROUND TRIP:
    A naive "ZCARD to check count, then ZADD if under the limit" sequence is a classic
    TOCTOU race: two concurrent requests on two different replicas could both observe a
    count under the limit and both add, exceeding max_requests. Instead, every increment()
    call optimistically prunes expired entries and adds its own timestamp in a single
    Redis MULTI/EXEC transaction (atomic from Redis's perspective — no other client's
    commands can interleave within it), then reads back the resulting count. If that count
    exceeds max_requests, the just-added entry is removed in a follow-up command so denied
    requests never permanently occupy a window slot.
    """

    _KEY_PREFIX = "rl:"

    def __init__(
        self,
        redis_url: str | None = None,
        client: "aioredis.Redis | None" = None,
    ) -> None:
        if client is not None:
            self._client = client
        elif aioredis is not None:
            from app.config import settings

            self._client = aioredis.from_url(
                redis_url or settings.redis_url, decode_responses=True
            )
        else:
            raise RateLimitBackendError(
                "The 'redis' package is not installed. Install it (see requirements.txt) "
                "or configure RATE_LIMIT_BACKEND=memory."
            )

    def _redis_key(self, key: str) -> str:
        return f"{self._KEY_PREFIX}{key}"

    async def increment(
        self, key: str, window_seconds: int, max_requests: int
    ) -> RateLimitResult:
        if max_requests <= 0 or window_seconds <= 0:
            return RateLimitResult.unlimited()

        now = time.time()
        cutoff = now - window_seconds
        redis_key = self._redis_key(key)
        member = f"{now!r}:{secrets.token_hex(8)}"

        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(redis_key, "-inf", cutoff)
                pipe.zadd(redis_key, {member: now})
                pipe.zcard(redis_key)
                pipe.expire(redis_key, window_seconds)
                pipe.zrange(redis_key, 0, 0, withscores=True)
                results = await pipe.execute()
        except Exception as exc:
            raise RateLimitBackendError(
                f"Redis error during increment for key '{key}': {exc}"
            ) from exc

        count = int(results[2])
        oldest_entries = results[4]
        oldest = float(oldest_entries[0][1]) if oldest_entries else now

        if count > max_requests:
            # This request's own addition pushed the window over the limit; undo it so
            # denied requests never permanently occupy a sliding-window slot.
            try:
                await self._client.zrem(redis_key, member)
            except Exception as exc:
                raise RateLimitBackendError(
                    f"Redis error rolling back denied request for key '{key}': {exc}"
                ) from exc
            reset_at = int(oldest + window_seconds)
            retry_after = max(1, int(math.ceil((oldest + window_seconds) - now)))
            return RateLimitResult(
                allowed=False,
                limit=max_requests,
                remaining=0,
                reset=reset_at,
                retry_after=retry_after,
            )

        remaining = max(0, max_requests - count)
        reset_at = int(oldest + window_seconds)
        return RateLimitResult(
            allowed=True,
            limit=max_requests,
            remaining=remaining,
            reset=reset_at,
            retry_after=0,
        )

    async def get(self, key: str) -> RateLimitResult:
        now = time.time()
        redis_key = self._redis_key(key)
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(redis_key, "-inf", now)
                pipe.zcard(redis_key)
                pipe.zrange(redis_key, 0, 0, withscores=True)
                results = await pipe.execute()
        except Exception as exc:
            raise RateLimitBackendError(
                f"Redis error during get for key '{key}': {exc}"
            ) from exc

        # get() has no window/max_requests context (interface parity with MemoryRateLimitBackend,
        # which is never actually called with a window in practice either); report unlimited when
        # there is no tracked state, matching MemoryRateLimitBackend.get()'s behavior for absent keys.
        count = int(results[1])
        if count == 0:
            return RateLimitResult.unlimited()
        oldest_entries = results[2]
        oldest = float(oldest_entries[0][1]) if oldest_entries else now
        return RateLimitResult(
            allowed=True,
            limit=count,
            remaining=0,
            reset=int(oldest),
            retry_after=0,
        )

    async def reset(self, key: str) -> None:
        try:
            await self._client.delete(self._redis_key(key))
        except Exception as exc:
            raise RateLimitBackendError(
                f"Redis error during reset for key '{key}': {exc}"
            ) from exc

    async def ttl(self, key: str) -> int:
        """
        Return the Redis key's own remaining TTL (refreshed on every increment() call to
        window_seconds). This approximates "time until this key's tracked window is fully
        clear" — unlike MemoryRateLimitBackend.ttl(), which is computed from the oldest
        tracked timestamp, this reflects time-since-last-request. No current caller in this
        codebase depends on exact TTL semantics; this is provided for interface parity and
        observability tooling.
        """
        try:
            raw_ttl = await self._client.ttl(self._redis_key(key))
        except Exception as exc:
            raise RateLimitBackendError(
                f"Redis error during ttl for key '{key}': {exc}"
            ) from exc
        return raw_ttl if raw_ttl and raw_ttl > 0 else -1

    async def get_active_key_count(self) -> int:
        try:
            count = 0
            async for _ in self._client.scan_iter(
                match=f"{self._KEY_PREFIX}*", count=500
            ):
                count += 1
            return count
        except Exception as exc:
            raise RateLimitBackendError(
                f"Redis error during get_active_key_count: {exc}"
            ) from exc

    async def clear(self) -> None:
        """Clear all rate limit data tracked by this backend (test isolation / admin reset)."""
        try:
            keys = [
                key
                async for key in self._client.scan_iter(
                    match=f"{self._KEY_PREFIX}*", count=500
                )
            ]
            if keys:
                await self._client.delete(*keys)
        except Exception as exc:
            raise RateLimitBackendError(f"Redis error during clear: {exc}") from exc

    async def aclose(self) -> None:
        """Close the underlying Redis connection pool (test/shutdown cleanup)."""
        try:
            await self._client.aclose()
        except Exception:
            pass
