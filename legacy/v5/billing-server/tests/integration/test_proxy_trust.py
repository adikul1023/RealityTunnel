import pytest
import httpx
from app.main import app
from app.config import settings
from fastapi import Request
from fastapi.responses import JSONResponse

# Create a dummy endpoint to echo back the client IP determined by the app
@app.get("/_test/ip")
async def echo_ip(request: Request):
    # This must reflect the middleware's logic
    client_ip = request.state.client_ip if hasattr(request.state, "client_ip") else "unknown"
    return JSONResponse({"client_ip": client_ip})

@pytest.fixture
def override_proxy_settings():
    # Save original
    orig_trust = getattr(settings, "trust_proxy", False)
    orig_ips = getattr(settings, "trusted_proxy_ips", "")
    
    # Set to true and set trusted proxy subnet (e.g. Docker's 172.28.0.0/16)
    settings.trust_proxy = True
    settings.trusted_proxy_ips = "172.28.0.0/16"
    
    yield
    
    # Restore
    settings.trust_proxy = orig_trust
    settings.trusted_proxy_ips = orig_ips

@pytest.fixture
def disable_proxy_settings():
    orig_trust = getattr(settings, "trust_proxy", False)
    settings.trust_proxy = False
    
    yield
    
    settings.trust_proxy = orig_trust

@pytest.mark.asyncio
async def test_proxy_trust_disabled(disable_proxy_settings):
    """
    If trust_proxy is False, X-Forwarded-For should be entirely ignored.
    """
    transport = httpx.ASGITransport(app=app, client=("10.0.0.5", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/_test/ip", headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp.status_code == 200
        assert resp.json()["client_ip"] == "10.0.0.5"

@pytest.mark.asyncio
async def test_proxy_trust_untrusted_peer(override_proxy_settings):
    """
    If the direct peer is NOT in trusted_proxy_ips, X-Forwarded-For must be ignored,
    even if trust_proxy is True.
    """
    # 10.0.0.5 is NOT in 172.28.0.0/16
    transport = httpx.ASGITransport(app=app, client=("10.0.0.5", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/_test/ip", headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp.status_code == 200
        assert resp.json()["client_ip"] == "10.0.0.5"

@pytest.mark.asyncio
async def test_proxy_trust_trusted_peer(override_proxy_settings):
    """
    If the direct peer IS trusted, X-Forwarded-For should be parsed.
    """
    transport = httpx.ASGITransport(app=app, client=("172.28.0.5", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/_test/ip", headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp.status_code == 200
        assert resp.json()["client_ip"] == "1.2.3.4"

@pytest.mark.asyncio
async def test_proxy_trust_multiple_proxies(override_proxy_settings):
    """
    If X-Forwarded-For has multiple hops, it must drop trusted proxies from the right,
    and pick the first untrusted IP (the real client).
    """
    transport = httpx.ASGITransport(app=app, client=("172.28.0.5", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Client (1.2.3.4) -> External Load Balancer (4.4.4.4) -> Internal Caddy (172.28.0.10) -> Uvicorn
        resp = await client.get("/_test/ip", headers={"X-Forwarded-For": "1.2.3.4, 4.4.4.4, 172.28.0.10"})
        assert resp.status_code == 200
        # 172.28.0.10 is trusted, so it moves left. 4.4.4.4 is NOT trusted, so it stops there.
        # Wait, the application should return 4.4.4.4 because it doesn't trust 4.4.4.4!
        # Let's see what it actually returns.
        assert resp.json()["client_ip"] == "4.4.4.4"

@pytest.mark.asyncio
async def test_proxy_trust_malformed_chain(override_proxy_settings):
    """
    Malformed chains should fallback to peer IP if it can't parse safely, or just ignore the malformed part.
    """
    transport = httpx.ASGITransport(app=app, client=("172.28.0.5", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/_test/ip", headers={"X-Forwarded-For": "not-an-ip, 1.2.3.4"})
        assert resp.status_code == 200
        assert resp.json()["client_ip"] == "1.2.3.4"

@pytest.mark.asyncio
async def test_proxy_trust_ipv6(override_proxy_settings):
    """
    IPv6 addresses should be handled correctly.
    """
    transport = httpx.ASGITransport(app=app, client=("172.28.0.5", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/_test/ip", headers={"X-Forwarded-For": "2001:db8::1"})
        assert resp.status_code == 200
        assert resp.json()["client_ip"] == "2001:db8::1"
