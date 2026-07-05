"""
tests/security/test_proxy_trust.py — Regression tests for Finding H-2.

app.rate_limit.middleware.RateLimitMiddleware._extract_client_ip previously trusted the
leftmost X-Forwarded-For entry unconditionally whenever settings.trust_proxy was True,
with no verification that the immediate TCP peer was actually a known reverse proxy. Since
the leftmost entry is the original, client-supplied value in the standard append
convention, this allowed trivial per-IP rate-limit and IP-ban bypass by spoofing a
different X-Forwarded-For header on every request.

These tests prove:
  1. An untrusted peer's spoofed X-Forwarded-For header is ignored entirely; the actual
     socket peer address is used instead.
  2. A trusted peer's X-Forwarded-For chain is parsed correctly using the rightmost
     non-trusted-proxy hop (not the leftmost, client-supplied hop).
  3. CIDR ranges in trusted_proxy_ips are honored.
  4. When trust_proxy is disabled (the default), forwarded headers are never consulted at
     all, regardless of trusted_proxy_ips.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from app.config import settings
from app.rate_limit.middleware import RateLimitMiddleware
from fastapi import Request


def make_request(peer_ip: str, headers: dict[str, str] | None = None) -> Request:
    """Build a minimal Starlette/FastAPI Request with a controlled peer IP and headers."""
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/auth/login",
        "headers": raw_headers,
        "client": (peer_ip, 54321),
    }
    return Request(scope)


@pytest.fixture
def middleware() -> RateLimitMiddleware:
    return RateLimitMiddleware(app=None)  # type: ignore[arg-type]


def test_untrusted_peer_spoofed_xff_is_ignored(middleware: RateLimitMiddleware):
    """
    Regression test for Finding H-2 (core vulnerability).

    A request arriving directly from an untrusted peer with a spoofed X-Forwarded-For
    header must resolve to the actual peer IP, never the attacker-supplied header value.
    """
    request = make_request("203.0.113.9", headers={"X-Forwarded-For": "6.6.6.6"})

    with (
        patch.object(settings, "trust_proxy", True),
        patch.object(settings, "trusted_proxy_ips", "10.0.0.1"),
    ):
        extracted = middleware._extract_client_ip(request)

    assert extracted == "203.0.113.9"
    assert extracted != "6.6.6.6"


def test_trust_proxy_disabled_ignores_headers_entirely(middleware: RateLimitMiddleware):
    """
    When trust_proxy is disabled (the default), forwarded headers must never be consulted,
    even if trusted_proxy_ips happens to be configured (e.g. leftover config).
    """
    request = make_request("203.0.113.9", headers={"X-Forwarded-For": "6.6.6.6"})

    with (
        patch.object(settings, "trust_proxy", False),
        patch.object(settings, "trusted_proxy_ips", "203.0.113.9"),
    ):
        extracted = middleware._extract_client_ip(request)

    assert extracted == "203.0.113.9"


def test_trusted_peer_uses_rightmost_non_trusted_hop(middleware: RateLimitMiddleware):
    """
    Regression test for Finding H-2 (correct proxy-chain parsing).

    With a trusted immediate peer and a multi-hop X-Forwarded-For chain
    ("original_client, proxy_a"), the rightmost hop that is itself a trusted proxy must be
    skipped, and the first non-trusted hop (the real original client) must be returned —
    never the leftmost hop blindly.
    """
    request = make_request(
        "10.0.0.2",
        headers={"X-Forwarded-For": "1.2.3.4, 10.0.0.1"},
    )

    with (
        patch.object(settings, "trust_proxy", True),
        patch.object(settings, "trusted_proxy_ips", "10.0.0.1,10.0.0.2"),
    ):
        extracted = middleware._extract_client_ip(request)

    assert extracted == "1.2.3.4"


def test_trusted_peer_cidr_range_is_honored(middleware: RateLimitMiddleware):
    """CIDR notation in trusted_proxy_ips must be honored, not just exact IP matches."""
    request = make_request(
        "10.5.6.7",
        headers={"X-Forwarded-For": "9.9.9.9"},
    )

    with (
        patch.object(settings, "trust_proxy", True),
        patch.object(settings, "trusted_proxy_ips", "10.0.0.0/8"),
    ):
        extracted = middleware._extract_client_ip(request)

    assert extracted == "9.9.9.9"


def test_trusted_peer_without_xff_falls_back_to_x_real_ip(
    middleware: RateLimitMiddleware,
):
    """A trusted peer without X-Forwarded-For but with X-Real-IP must use that header."""
    request = make_request(
        "10.0.0.1",
        headers={"X-Real-IP": "8.8.8.8"},
    )

    with (
        patch.object(settings, "trust_proxy", True),
        patch.object(settings, "trusted_proxy_ips", "10.0.0.1"),
    ):
        extracted = middleware._extract_client_ip(request)

    assert extracted == "8.8.8.8"


def test_untrusted_peer_x_real_ip_also_ignored(middleware: RateLimitMiddleware):
    """An untrusted peer's spoofed X-Real-IP must also be ignored, not just X-Forwarded-For."""
    request = make_request(
        "203.0.113.9",
        headers={"X-Real-IP": "8.8.8.8"},
    )

    with (
        patch.object(settings, "trust_proxy", True),
        patch.object(settings, "trusted_proxy_ips", "10.0.0.1"),
    ):
        extracted = middleware._extract_client_ip(request)

    assert extracted == "203.0.113.9"


def test_empty_trusted_proxy_ips_trusts_nothing(middleware: RateLimitMiddleware):
    """
    trust_proxy=True with an empty trusted_proxy_ips must trust no peer at all — a safe
    fail-closed default rather than silently trusting every peer.
    """
    request = make_request("10.0.0.1", headers={"X-Forwarded-For": "6.6.6.6"})

    with (
        patch.object(settings, "trust_proxy", True),
        patch.object(settings, "trusted_proxy_ips", ""),
    ):
        extracted = middleware._extract_client_ip(request)

    assert extracted == "10.0.0.1"
