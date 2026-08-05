"""
tests/core/test_proxy_middleware.py

Regression tests protecting the X-Forwarded-For trust parsing logic.
Ensures that we do not blindly trust client-supplied X-Forwarded-For headers
unless the immediate socket connection is from a trusted proxy subnet.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.config import Settings
from app.rate_limit.middleware import RateLimitMiddleware

# A minimal app with just the proxy middleware for hermetic testing.
_inner_app = FastAPI()
_inner_app.add_middleware(RateLimitMiddleware)

@_inner_app.get("/")
async def root(request: Request):
    # request.state.client_ip is populated by RateLimitMiddleware
    return JSONResponse({"client_ip": request.state.client_ip})

def create_client(peer_ip: str) -> TestClient:
    """
    Wrap the FastAPI app with an ASGI middleware that forcibly sets the
    'client' tuple in the ASGI scope to simulate a specific immediate socket peer.
    """
    async def asgi_wrapper(scope, receive, send):
        if scope["type"] == "http":
            scope["client"] = (peer_ip, 12345)
        await _inner_app(scope, receive, send)
    
    return TestClient(asgi_wrapper)


class TestProxyMiddlewareTrustLogic:
    @pytest.fixture(autouse=True)
    def _patch_settings(self, monkeypatch):
        # By default, mock the settings accessed inside middleware to trust 172.28.0.0/16
        # The middleware accesses config via `from app.config import settings`
        # But `RateLimitMiddleware` accesses `settings` globally, so we mock it.
        mock_settings = Settings(
            trust_proxy=True,
            trusted_proxy_ips="172.28.0.0/16"
        )
        monkeypatch.setattr("app.rate_limit.middleware.settings", mock_settings)

    def test_untrusted_peer_is_not_trusted(self):
        """
        Remote peer = 8.8.8.8
        Header: X-Forwarded-For: 1.2.3.4
        Expected client IP: 8.8.8.8 (The untrusted peer's actual IP, header ignored)
        """
        client = create_client("8.8.8.8")
        
        response = client.get("/", headers={"X-Forwarded-For": "1.2.3.4"})
        assert response.status_code == 200
        assert response.json() == {"client_ip": "8.8.8.8"}

    def test_trusted_peer_extracts_correct_hop(self):
        """
        Remote peer = 172.28.0.2 (Caddy in trusted subnet)
        Header: X-Forwarded-For: 203.0.113.4, 172.28.0.2
        Expected: 203.0.113.4
        """
        client = create_client("172.28.0.2")
        
        response = client.get("/", headers={
            "X-Forwarded-For": "203.0.113.4, 172.28.0.2"
        })
        assert response.status_code == 200
        assert response.json() == {"client_ip": "203.0.113.4"}

    def test_attacker_spoofs_header_through_trusted_proxy(self):
        """
        Remote peer = 172.28.0.2 (Caddy)
        Header: X-Forwarded-For: 1.2.3.4, 203.0.113.4
        Expected: 203.0.113.4
        """
        client = create_client("172.28.0.2")
        
        response = client.get("/", headers={
            "X-Forwarded-For": "1.2.3.4, 203.0.113.4"
        })
        assert response.status_code == 200
        assert response.json() == {"client_ip": "203.0.113.4"}

    def test_trust_proxy_disabled_globally(self, monkeypatch):
        """
        When trust_proxy is False, even connections from the 'trusted' subnet
        have their forwarded headers ignored.
        """
        mock_settings = Settings(trust_proxy=False, trusted_proxy_ips="172.28.0.0/16")
        monkeypatch.setattr("app.rate_limit.middleware.settings", mock_settings)
        
        client = create_client("172.28.0.2")
        
        response = client.get("/", headers={"X-Forwarded-For": "203.0.113.4"})
        assert response.status_code == 200
        assert response.json() == {"client_ip": "172.28.0.2"}

    def test_x_real_ip_used_when_trusted(self):
        """
        If X-Forwarded-For is missing but X-Real-IP is present and the peer is trusted,
        it uses X-Real-IP.
        """
        client = create_client("172.28.0.2")
        
        response = client.get("/", headers={"X-Real-IP": "203.0.113.4"})
        assert response.status_code == 200
        assert response.json() == {"client_ip": "203.0.113.4"}
