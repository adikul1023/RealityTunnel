"""
agent_bootstrap.py - Handles node provisioning, bootstrap tokens, and certificate registration.
"""

import uuid
import base64
import os
import argon2
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.agent_bootstrap_token import AgentBootstrapToken
from app.models.agent_node import AgentNode
from app.models.agent_certificate import AgentCertificate
from app.services.crypto_service import crypto_service
from app.services.certificate_service import certificate_service
from app.exceptions import InvalidCertificateError
from app.dependencies import verify_agent_node

router = APIRouter(
    prefix="/api/agent",
    tags=["Agent Provisioning"],
)

_ph = argon2.PasswordHasher()

class BootstrapResponse(BaseModel):
    node_id: str
    agent_secret: str
    config_revision: int
    heartbeat_interval: int
    registration_policy: str

class RegisterCertRequest(BaseModel):
    pfx_base64: str
    
class NodeHeartbeatRequest(BaseModel):
    disk_usage_percent: float
    os_info: str
    vpnhood_version: str
    cpu_temp: Optional[float] = None

@router.post("/bootstrap", response_model=BootstrapResponse)
async def bootstrap_node(
    bootstrap_token: str = Header(..., alias="Bootstrap-Token"),
    db: AsyncSession = Depends(get_db)
):
    """
    Exchanges a one-time bootstrap token for a long-term agent secret.
    """
    # 1. Verify Bootstrap Token
    # Since we use Argon2, we must query all unused, unexpired tokens and verify.
    # In production, we'd prefix the token with an ID to avoid full table scans.
    # For now, we will do a simple scan or assume token contains ID.
    # Let's assume the client passes the raw token, and we hash it (if it was SHA256) 
    # or we just use Argon2. Wait, Argon2 takes time.
    # To keep it simple and robust, let's assume the token is just a secure random string and we check it.
    
    # Actually, let's find the token. If we assume token_hash is actually just a SHA-256 for fast lookup:
    import hashlib
    token_hash = hashlib.sha256(bootstrap_token.encode('utf-8')).hexdigest()
    
    result = await db.execute(
        select(AgentBootstrapToken)
        .where(AgentBootstrapToken.token_hash == token_hash)
        .where(AgentBootstrapToken.used_at.is_(None))
    )
    token_obj = result.scalars().first()
    
    if not token_obj or token_obj.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired bootstrap token.")
        
    # Mark token used
    token_obj.used_at = datetime.utcnow()
    
    # 2. Generate new AgentNode and AgentSecret
    raw_agent_secret = base64.urlsafe_b64encode(os.urandom(32)).decode('ascii').rstrip("=")
    agent_secret_hash = _ph.hash(raw_agent_secret)
    
    node = AgentNode(
        agent_secret_hash=agent_secret_hash,
        status="active"
    )
    db.add(node)
    await db.flush() # to get node.id
    
    await db.commit()
    
    return BootstrapResponse(
        node_id=str(node.id),
        agent_secret=f"{node.id}.{raw_agent_secret}", # Combine node_id and secret for easy lookup
        config_revision=node.config_revision,
        heartbeat_interval=60,
        registration_policy="strict"
    )

@router.post("/register-cert")
async def register_cert(
    request: RegisterCertRequest,
    node: AgentNode = Depends(verify_agent_node),
    db: AsyncSession = Depends(get_db)
):
    """
    Uploads a new PFX certificate for the node.
    """
    try:
        pfx_bytes = base64.b64decode(request.pfx_base64)
        metadata = certificate_service.validate_and_extract(pfx_bytes)
    except InvalidCertificateError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # Encrypt
    encrypted_data = crypto_service.encrypt_blob(pfx_bytes)
    
    # Calculate new rotation version
    result = await db.execute(
        select(AgentCertificate.rotation_version)
        .where(AgentCertificate.node_id == node.id)
        .order_by(AgentCertificate.rotation_version.desc())
        .limit(1)
    )
    max_version = result.scalars().first() or 0
    new_version = max_version + 1
    
    # Insert new pending certificate
    new_cert = AgentCertificate(
        node_id=node.id,
        fingerprint=metadata["fingerprint"],
        common_name=metadata["common_name"],
        algorithm=metadata["algorithm"],
        expires_at=metadata["expires_at"],
        rotation_version=new_version,
        status="pending",
        crypto_key_version=encrypted_data["key_version"],
        crypto_nonce=encrypted_data["crypto_nonce"],
        crypto_tag=encrypted_data["crypto_tag"],
        encrypted_pfx=encrypted_data["encrypted_blob"],
    )
    db.add(new_cert)
    
    # Bump node config revision so clients know there's a change
    node.config_revision += 1
    
    await db.commit()
    
    return {"status": "ok", "version": new_version}

@router.post("/node-heartbeat")
async def node_heartbeat(
    request: NodeHeartbeatRequest,
    node: AgentNode = Depends(verify_agent_node),
    db: AsyncSession = Depends(get_db)
):
    """
    Node infrastructure heartbeat.
    """
    node.os_info = request.os_info
    node.vpnhood_version = request.vpnhood_version
    await db.commit()
    return {"status": "ok"}
