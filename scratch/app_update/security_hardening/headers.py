"""
headers.py — Security Headers Middleware for Phase 3.5 Security Hardening & Production Defense.

Automatically injects configurable HTTP security headers onto all responses and tracks metrics.
"""
from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.observability.metrics import metrics_registry

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically attaches production security headers:
      - Strict-Transport-Security (HSTS)
      - Content-Security-Policy (CSP)
      - X-Frame-Options
      - X-Content-Type-Options
      - Referrer-Policy
      - Permissions-Policy
      - Cross-Origin-Opener-Policy (COOP)
      - Cross-Origin-Resource-Policy (CORP)
      - Cross-Origin-Embedder-Policy (COEP)
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        response = await call_next(request)

        if not getattr(settings, "security_headers_enabled", True):
            return response

        # Attach headers from configuration
        if getattr(settings, "security_hsts", None):
            response.headers["Strict-Transport-Security"] = settings.security_hsts
        if getattr(settings, "security_csp", None):
            response.headers["Content-Security-Policy"] = settings.security_csp
        if getattr(settings, "security_x_frame_options", None):
            response.headers["X-Frame-Options"] = settings.security_x_frame_options
        if getattr(settings, "security_x_content_type_options", None):
            response.headers["X-Content-Type-Options"] = settings.security_x_content_type_options
        if getattr(settings, "security_referrer_policy", None):
            response.headers["Referrer-Policy"] = settings.security_referrer_policy
        if getattr(settings, "security_permissions_policy", None):
            response.headers["Permissions-Policy"] = settings.security_permissions_policy
        if getattr(settings, "security_coop", None):
            response.headers["Cross-Origin-Opener-Policy"] = settings.security_coop
        if getattr(settings, "security_corp", None):
            response.headers["Cross-Origin-Resource-Policy"] = settings.security_corp
        if getattr(settings, "security_coep", None):
            response.headers["Cross-Origin-Embedder-Policy"] = settings.security_coep

        metrics_registry.inc_counter("security_headers_applied_total")
        return response
