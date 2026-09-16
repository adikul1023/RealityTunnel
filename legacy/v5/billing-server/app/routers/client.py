"""
client.py — Client Configuration & Update Endpoints

Provides VPN configuration, offline license blobs, and OTA update metadata to authenticated clients.
"""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_account
from app.models.account import Account
from app.models.device import Device
from app.security import JWTService

router = APIRouter(prefix="/api/client", tags=["Client"])


class VpnProfileDto(BaseModel):
    uuid: str = Field(..., description="VLESS UUID")
    server_host: str = Field(..., description="VPN Server Hostname")
    server_port: int = Field(..., description="VPN Server Port")
    public_key: str = Field(..., description="REALITY Public Key")
    short_id: str = Field(..., description="REALITY Short ID")
    sni: str = Field(..., description="Server Name Indication")
    preferred_dns: str | None = Field(None, description="DNS Server IP")


class LicenseBlobDto(BaseModel):
    payload: str = Field(..., description="Base64 encoded license payload")
    signature: str = Field(..., description="Ed25519 signature of the payload")


class ClientConfigResponse(BaseModel):
    vpn_profile: VpnProfileDto
    license_blob: LicenseBlobDto


from fastapi import Header
from app.services.provisioning.service import ProvisioningService
from app.dependencies import get_provisioning_service
from app.config import settings
from app.models.base import AccountStatus
from app.exceptions import EntityNotFoundError
from app.services.exceptions import ProvisioningSynchronizationError
import logging

logger = logging.getLogger(__name__)

@router.get(
    "/config",
    summary="Fetch VPN configuration and offline license blob",
    response_model=ClientConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def get_client_config(
    x_device_id: str | None = Header(None, alias="X-Device-ID", description="Registered device ID"),
    current_account: Account = Depends(get_current_account),
    provisioning: ProvisioningService = Depends(get_provisioning_service),
    db: AsyncSession = Depends(get_db),
) -> ClientConfigResponse:
    """
    Returns the VPN profile (for the client's VPN engine) and an offline License Blob 
    (for offline authorization when Oracle is unreachable).
    """
    # Verify Device
    if not x_device_id:
        raise HTTPException(status_code=400, detail="Missing X-Device-ID header")
    
    device_res = await db.execute(select(Device).where(Device.device_guid == x_device_id, Device.account_id == current_account.id))
    if not device_res.scalar_one_or_none():
        raise HTTPException(status_code=401, detail="Device not registered")
        
    # Verify Active Subscription
    if current_account.status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account requires an active subscription")

    try:
        identity = await provisioning.get_vpn_identity(current_account.id)
        logger.info(f"AUDIT DIAGNOSTIC: get_vpn_identity succeeded for {current_account.account_id}")
    except EntityNotFoundError:
        logger.warning(f"AUDIT DIAGNOSTIC: get_vpn_identity raised EntityNotFoundError for {current_account.account_id}. Attempting auto-provisioning.")
        try:
            await provisioning.provision_subscription(
                account_id=current_account.id,
                plan_id=current_account.plan_id,
                commit=True
            )
            identity = await provisioning.get_vpn_identity(current_account.id)
            logger.info(f"AUDIT DIAGNOSTIC: Auto-provisioning succeeded for {current_account.account_id}")
        except Exception as e:
            logger.error(f"Auto-provisioning failed for {current_account.account_id}: {e}")
            raise HTTPException(status_code=404, detail="VPN identity not found and could not be auto-provisioned")
    except ProvisioningSynchronizationError as e:
        logger.error(f"Upstream provider sync failed for {current_account.account_id}: {e}")
        raise HTTPException(status_code=502, detail="Upstream VPN provider synchronization failed. The service might be temporarily unreachable.")
    
    return ClientConfigResponse(
        vpn_profile=VpnProfileDto(
            uuid=identity.uuid,
            server_host=settings.vpn_edge_host,
            server_port=settings.vpn_edge_port,
            public_key=settings.vpn_edge_reality_public_key,
            short_id=settings.vpn_edge_reality_short_id,
            sni=settings.vpn_edge_reality_sni,
            preferred_dns=settings.vpn_preferred_dns,
        ),
        license_blob=LicenseBlobDto(
            payload="mock-payload",
            signature="mock-signature"
        )
    )


class ClientMeResponse(BaseModel):
    account_id: str
    status: str
    subscription_expires_at: datetime | None
    device_count: int
    plan: str
    email: str | None
    two_factor_enabled: bool


@router.get(
    "/me",
    summary="Retrieve full UI profile information for the authenticated account",
    response_model=ClientMeResponse,
    status_code=status.HTTP_200_OK,
)
async def get_client_me(
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
) -> ClientMeResponse:
    """
    Supersedes /api/auth/me by providing additional UI-specific details like device count and 2FA status.
    """
    res = await db.execute(
        select(func.count(Device.id)).where(Device.account_id == current_account.id)
    )
    device_count = res.scalar() or 0

    status_val = (
        current_account.status.value
        if hasattr(current_account.status, "value")
        else str(current_account.status)
    )

    return ClientMeResponse(
        account_id=current_account.account_id,
        status=status_val,
        subscription_expires_at=current_account.subscription_expires_at,
        device_count=device_count,
        plan=current_account.plan_id or "free",
        email=getattr(current_account, "email", None),
        two_factor_enabled=getattr(current_account, "totp_secret", None) is not None,
    )


class ClientUpdateResponse(BaseModel):
    latest_version: str
    mandatory: bool
    download_url: str
    release_notes: str


@router.get(
    "/update",
    summary="Check for OTA updates",
    response_model=ClientUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def get_client_update() -> ClientUpdateResponse:
    """
    Returns the latest version information for the client applications.
    """
    return ClientUpdateResponse(
        latest_version="1.0.0",
        mandatory=False,
        download_url="https://stealthy.co.in/download",
        release_notes="Initial release"
    )

class VpnHoodTokenResponse(BaseModel):
    access_key: str

@router.post(
    "/vpnhood/token",
    summary="Generate a dynamic VPNHood access key",
    response_model=VpnHoodTokenResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_vpnhood_token(
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
) -> VpnHoodTokenResponse:
    from app.models.agent_node import AgentNode
    from app.models.agent_certificate import AgentCertificate
    import base64
    import json
    import os
    
    result = await db.execute(select(AgentNode).where(AgentNode.status == "active").limit(1))
    node = result.scalar_one_or_none()
    
    cert = None
    if node:
        cert_result = await db.execute(
            select(AgentCertificate).where(AgentCertificate.node_id == node.id, AgentCertificate.status == "active").limit(1)
        )
        cert = cert_result.scalar_one_or_none()
        server_secret = base64.b64encode(node.id.bytes).decode('ascii')
        server_host = node.public_ip or settings.vpn_edge_host
    else:
        # Fallback for new users / testing environments where no active node exists
        mock_node_id = uuid.uuid4()
        server_secret = base64.b64encode(mock_node_id.bytes).decode('ascii')
        server_host = settings.vpn_edge_host
    
    client_secret = base64.b64encode(os.urandom(16)).decode('ascii')
    token_id = str(uuid.uuid4())
    
    cert_hash = None
    is_valid_host = True
    if cert and cert.fingerprint:
        try:
            cert_hash = base64.b64encode(bytes.fromhex(cert.fingerprint.replace(":", ""))).decode('ascii')
            is_valid_host = False
        except Exception:
            pass

    server_port = settings.vpn_edge_port
    
    token_dict = {
        'v': 4,
        'name': f"RealityTunnel-{current_account.account_id[:8]}",
        'sid': str(current_account.id),
        'tid': token_id,
        'iat': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        'sec': client_secret,
        'ser': {
            'ct': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'hname': server_host,
            'hport': server_port,
            'isv': is_valid_host,
            'sec': server_secret,
            'ch': cert_hash,
            'urls': [],
            'ep': [f"{server_host}:{server_port}"],
            'ep_st': 2,
            'loc': ["Global/Auto"],
            'loc2': ["Global/Auto"]
        },
        'tags': []
    }
    
    json_str = json.dumps(token_dict, separators=(',', ':'))
    access_key = 'vh://' + base64.b64encode(json_str.encode('utf-8')).decode('ascii')
    
    return VpnHoodTokenResponse(access_key=access_key)
