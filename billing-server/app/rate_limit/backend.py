"""
app/rate_limit/backend.py — Storage backend abstractions for rate limiting (Phase 3.3).
Provides RateLimitBackend interface and MemoryRateLimitBackend with Sliding Window Log.
"""
from __future__ import annotations

import asyncio
import math
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Any

from app.rate_limit.exceptions import RateLimitBackendError
from app.rate_limit.models import RateLimitResult


class RateLimitBackend(ABC):
    """Abstract rate limit storage backend interface designed for Redis compatibility."""

    @abstractmethod
    async def increment(self, key: str, window_seconds: int, max_requests: int) -> RateLimitResult:
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

    async def _prune_key_locked(self, key: str, now: float) -> tuple[deque[float], int, int] | None:
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

    async def increment(self, key: str, window_seconds: int, max_requests: int) -> RateLimitResult:
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
            retry_after = max(1, int(math.ceil((oldest + window_seconds) - now))) if not allowed else 0
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
