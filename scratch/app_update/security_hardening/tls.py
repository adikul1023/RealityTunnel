"""
tls.py — TLS & HTTPS enforcement utilities for Phase 3.5 Security Hardening & Production Defense.

Enforces HTTPS for webhooks and callback URLs in production environments and tracks TLS validation failures.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from app.config import settings
from app.observability.metrics import metrics_registry
from app.security_hardening.exceptions import TLSValidationError

logger = logging.getLogger(__name__)


def validate_tls_url(url: str, url_type: str = "url") -> None:
    """
    Validate that a target URL uses HTTPS when running in the production profile.

    Raises:
        TLSValidationError: If running in production and scheme is not https.
    """
    if not url:
        return

    is_production = getattr(settings, "environment", "development").lower() == "production"
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()

    if is_production and scheme != "https":
        metrics_registry.inc_counter("tls_validation_failures_total")
        logger.warning(
            "Insecure %s target rejected in production profile (scheme=%s). Must use HTTPS.",
            url_type,
            scheme,
        )
        raise TLSValidationError(
            f"Insecure {url_type} rejected in production mode: URL must use https:// scheme."
        )


def get_secure_client_ssl_context() -> dict[str, any]:
    """
    Return secure HTTP client TLS configuration options.
    Ensures certificate verification is strictly enabled.
    """
    return {
        "verify": True,
        "follow_redirects": False,  # Prevent redirect downgrade attacks
    }
