"""
app/rate_limit/storage.py — Central storage backend provider for rate limiting (Phase 3.3).
Provides singleton access to active RateLimitBackend, allowing seamless future Redis migration.
"""
from __future__ import annotations

from functools import lru_cache

from app.rate_limit.backend import MemoryRateLimitBackend, RateLimitBackend


@lru_cache
def get_rate_limit_backend() -> RateLimitBackend:
    """
    Return the configured RateLimitBackend singleton instance.
    In development and Phase 3.3, uses MemoryRateLimitBackend (Sliding Window Log).
    In future phases, this factory will inspect settings to initialize RedisRateLimitBackend.
    """
    return MemoryRateLimitBackend()
