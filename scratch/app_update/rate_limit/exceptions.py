"""
app/rate_limit/exceptions.py — Rate limiting exception definitions (Phase 3.3).
Defines HTTP 429 RateLimitExceeded exception with standard headers and retry_after payload.
"""
from __future__ import annotations

from fastapi import HTTPException, status


class RateLimitExceeded(HTTPException):
    """
    Raised when a caller exceeds their permitted rate limit.
    Enforces HTTP 429 status code and injects required rate limiting headers.
    """

    def __init__(
        self,
        retry_after: int = 0,
        limit: int = 0,
        remaining: int = 0,
        reset: int = 0,
        detail: str = "Rate limit exceeded",
    ) -> None:
        self.retry_after = max(1, retry_after) if retry_after > 0 else 1
        self.limit = limit
        self.remaining = remaining
        self.reset = reset

        headers: dict[str, str] = {
            "Retry-After": str(self.retry_after),
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset),
        }
        # The user specification requires response body to contain detail and retry_after:
        # {"detail": "Rate limit exceeded", "retry_after": 12}
        # Notice that in FastAPI, if detail is a dict or string, we can customize it or handle it in an exception handler.
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"detail": detail, "retry_after": self.retry_after},
            headers=headers,
        )


class RateLimitBackendError(Exception):
    """Raised when a rate limit storage backend experiences a fault or disconnection."""
