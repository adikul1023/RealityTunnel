import pytest
from httpx import AsyncClient
from fastapi import status
from app.config import settings


@pytest.mark.asyncio
async def test_vpnhood_agent_sessions_unauthorized(async_client: AsyncClient):
    """Test that agent endpoints require the agent token."""
    response = await async_client.post("/api/agent/sessions", json={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Missing Authorization header"


@pytest.mark.asyncio
async def test_vpnhood_agent_sessions_invalid_token(async_client: AsyncClient):
    """Test that agent endpoints reject invalid token."""
    response = await async_client.post(
        "/api/agent/sessions", 
        json={},
        headers={"Authorization": "Bearer INVALID_TOKEN"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid Agent token"


@pytest.mark.asyncio
async def test_vpnhood_agent_create_session(async_client: AsyncClient):
    """Test creating a VPNHood session with a valid token."""
    # Assuming test config sets agent_secret to something known, e.g., 'TEST_AGENT_SECRET'
    agent_token = settings.agent_secret.get_secret_value()
    
    payload = {
        "tokenId": "valid-token-123",
        "clientInfo": {
            "clientId": "client123",
            "osName": "Windows",
            "osVersion": "11",
            "appVersion": "1.0",
            "buildNumber": 100
        },
        "encryptedClientId": "encrypted123",
        "protocolVersion": 1,
        "hostEndPoint": "server.example.com",
    }
    
    response = await async_client.post(
        "/api/agent/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {agent_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["errorCode"] == 0 # Success
    assert isinstance(data["sessionId"], int)
    assert "sessionKey" in data
    assert data["protocolVersion"] == 1


@pytest.mark.asyncio
async def test_vpnhood_agent_status_report(async_client: AsyncClient):
    """Test that status report endpoint handles data correctly."""
    agent_token = settings.agent_secret.get_secret_value()
    
    payload = {
        "sessionCount": 10,
        "tcpConnectionCount": 50,
        "udpConnectionCount": 20,
        "usedMemory": 1024,
        "threadCount": 10,
        "tunnelSpeed": {
            "sent": 1000,
            "received": 2000
        }
    }
    
    response = await async_client.post(
        "/api/agent/status",
        json=payload,
        headers={"Authorization": f"Bearer {agent_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "configCode" in data
