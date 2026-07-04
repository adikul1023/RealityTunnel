"""
app/rate_limit/models.py — Data structures for Rate Limiting & Abuse Protection (Phase 3.3).
Defines key types, rule definitions, and evaluation results.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class KeyType(str, Enum):
    """Supported tracking dimensions for rate limiting."""
    IP = "ip"
    ACCOUNT = "account"
    DEVICE = "device"
    ADMIN = "admin"
    ENDPOINT = "endpoint"


@dataclass(frozen=True)
class RateLimitRule:
    """Represents a parsed rate limit rule (e.g., '10/minute' or '20/hour')."""
    limit_str: str
    max_requests: int
    window_seconds: int
    unlimited: bool = False

    _PERIOD_MAP: ClassVar[dict[str, int]] = {
        "second": 1,
        "sec": 1,
        "s": 1,
        "minute": 60,
        "min": 60,
        "m": 60,
        "hour": 3600,
        "hr": 3600,
        "h": 3600,
        "day": 86400,
        "d": 86400,
    }

    @classmethod
    def parse(cls, limit_str: str) -> RateLimitRule:
        """Parse a string like '10/minute', '20/hour', or 'unlimited'."""
        cleaned = limit_str.strip().lower()
        if not cleaned or cleaned == "unlimited" or cleaned == "0":
            return cls(limit_str=cleaned, max_requests=0, window_seconds=0, unlimited=True)

        parts = cleaned.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid rate limit format: '{limit_str}'. Expected 'count/period' or 'unlimited'.")

        try:
            max_requests = int(parts[0].strip())
        except ValueError as exc:
            raise ValueError(f"Invalid request count in rate limit rule: '{limit_str}'") from exc

        period_raw = parts[1].strip().rstrip("s")  # handle plural 'minutes', 'hours'
        window_seconds = cls._PERIOD_MAP.get(period_raw)
        if window_seconds is None:
            raise ValueError(
                f"Unknown period '{parts[1]}' in rule '{limit_str}'. Supported: second, minute, hour, day."
            )

        return cls(
            limit_str=cleaned,
            max_requests=max_requests,
            window_seconds=window_seconds,
            unlimited=False,
        )


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a rate limit check against a storage backend."""
    allowed: bool
    limit: int
    remaining: int
    reset: int        # Epoch timestamp (seconds) when remaining capacity resets
    retry_after: int  # Seconds caller must wait if denied (0 if allowed)

    @classmethod
    def unlimited(cls) -> RateLimitResult:
        now = int(time.time())
        return cls(allowed=True, limit=999999, remaining=999999, reset=now + 3600, retry_after=0)
