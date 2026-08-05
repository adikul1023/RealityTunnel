import pytest
import uuid
import base64
import os
from datetime import datetime, timedelta
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.models.agent_bootstrap_token import AgentBootstrapToken
from app.models.agent_node import AgentNode
from app.models.agent_certificate import AgentCertificate

@pytest.mark.asyncio
async def test_agent_lifecycle_e2e(async_client: AsyncClient, db_session: AsyncSession):
    """
    E2E Integration test covering:
    bootstrap -> register-cert -> configure -> VPNHood loads certificate -> status heartbeat -> pending promoted to active
    """
    import hashlib
    # 1. Setup a valid bootstrap token in DB
    raw_token = f"e2e_test_token_{uuid.uuid4()}"
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    
    token = AgentBootstrapToken(
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=1),
        created_by=uuid.uuid4(),
        purpose="e2e test"
    )
    db_session.add(token)
    await db_session.commit()
    
    # 2. Bootstrap node
    response = await async_client.post(
        "/api/agent/bootstrap",
        headers={"Bootstrap-Token": raw_token}
    )
    assert response.status_code == status.HTTP_200_OK
    bootstrap_data = response.json()
    agent_secret = bootstrap_data["agent_secret"]
    node_id = bootstrap_data["node_id"]
    
    auth_headers = {"Authorization": f"Bearer {agent_secret}"}
    
    # 3. Register Certificate
    # We patch certificate_service.validate_and_extract to avoid needing a real PFX
    mock_cert_metadata = {
        "fingerprint": "mock_sha256",
        "common_name": f"CN=VPNHood-Node-{node_id}",
        "subject_alternative_names": ["localhost"],
        "algorithm": "RSA 2048",
        "expires_at": datetime.utcnow() + timedelta(days=365)
    }
    
    with patch("app.routers.agent_bootstrap.certificate_service.validate_and_extract", return_value=mock_cert_metadata):
        dummy_pfx = base64.b64encode(b"dummy_pfx_content").decode("ascii")
        response = await async_client.post(
            "/api/agent/register-cert",
            json={"pfx_base64": dummy_pfx},
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_200_OK
        
    # Check DB - Cert should be "pending"
    await db_session.refresh(token) # Just to ensure session is active
    from sqlalchemy import select
    res = await db_session.execute(select(AgentCertificate).where(AgentCertificate.node_id == uuid.UUID(node_id)))
    cert = res.scalars().first()
    assert cert is not None
    assert cert.status == "pending"
    
    # 4. Configure Endpoint (VPNHood fetching cert)
    response = await async_client.post(
        "/api/agent/configure",
        json={"machineName": "test-machine", "osVersion": "1.0"},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    config_data = response.json()
    assert "Certificates" in config_data
    assert len(config_data["Certificates"]) == 1
    assert config_data["Certificates"][0]["CommonName"] == mock_cert_metadata["common_name"]
    # Verify the returned cert can be base64 decoded back to our original content
    returned_raw = base64.b64decode(config_data["Certificates"][0]["RawData"]).decode('ascii')
    assert returned_raw == "dummy_pfx_content"
    
    # 5. Status Heartbeat (VPNHood reporting successful load -> Promotes Pending to Active)
    response = await async_client.post(
        "/api/agent/status",
        json={
            "sessionCount": 0,
            "tcpConnectionCount": 0,
            "udpConnectionCount": 0,
            "usedMemory": 1024,
            "threadCount": 1,
            "tunnelSpeed": {"sent": 0, "received": 0},
            "configError": None # Important: no config error!
        },
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 6. Verify Promotion in DB
    await db_session.refresh(cert)
    assert cert.status == "active"
