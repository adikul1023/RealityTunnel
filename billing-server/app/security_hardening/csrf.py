"""
csrf.py — Cross-Site Request Forgery (CSRF) defense for browser-facing endpoints (Phase 3.5).

Protects administrative browser endpoints against CSRF attacks while preserving token authentication
for programmatic API clients.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.observability.metrics import metrics_registry
from app.security_hardening.exceptions import CSRFValidationError

logger = logging.getLogger(__name__)


def get_allowed_origins() -> set[str]:
    """Parse configured allowed CSRF origins."""
    raw = getattr(settings, "csrf_allowed_origins", "http://localhost:8080,http://127.0.0.1:8080")
    return {o.strip().lower() for o in raw.split(",") if o.strip()}


def validate_csrf_protection(request: Request) -> None:
    """
    Validate CSRF defenses for state-changing administrative requests.

    Rules:
      1. Safe methods (GET, HEAD, OPTIONS) are exempt.
      2. If neither Origin nor Cookie is present (pure programmatic Bearer token client), exempt.
      3. If Origin or Referer header is present on an admin endpoint, it must match an allowed origin
         or target host.
      4. If Cookie credentials are used for state-changing admin operations, Origin/Referer must be verified.
    """
    if not getattr(settings, "csrf_protection_enabled", True):
        return

    if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
        return

    path = request.url.path
    if not path.startswith("/api/admin/"):
        return

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    cookie = request.headers.get("cookie")
    auth_header = request.headers.get("authorization")

    # If pure Bearer token without cookies or origin, API client is token-authenticated
    if auth_header and auth_header.lower().startswith("bearer ") and not cookie and not origin and not referer:
        return

    allowed_origins = get_allowed_origins()
    host_url = f"{request.url.scheme}://{request.url.netloc}".lower()
    allowed_origins.add(host_url)

    target_origin: str | None = None
    if origin:
        target_origin = origin.strip().lower()
    elif referer:
        parsed = urlparse(referer)
        target_origin = f"{parsed.scheme}://{parsed.netloc}".lower()

    if target_origin:
        if target_origin not in allowed_origins:
            metrics_registry.inc_counter("csrf_rejections_total")
            logger.warning(
                "CSRF rejection: Origin/Referer '%s' not allowed for admin path=%s",
                target_origin,
                path,
            )
            raise CSRFValidationError(
                f"CSRF validation failed: untrusted origin '{target_origin}'."
            )
    elif cookie and not auth_header:
        # Browser cookie request without Origin or Referer header is suspicious for state changes
        metrics_registry.inc_counter("csrf_rejections_total")
        logger.warning(
            "CSRF rejection: missing Origin/Referer on cookie-authenticated request path=%s",
            path,
        )
        raise CSRFValidationError(
            "CSRF validation failed: missing Origin or Referer header on cookie-backed request."
        )


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    ASGI Middleware that intercepts administrative requests and invokes CSRF validation.
    """
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> any:
        try:
            validate_csrf_protection(request)
        except CSRFValidationError as exc:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=403,
                content={"detail": exc.message, "error_type": "csrf_validation_error"},
            )
        return await call_next(request)
