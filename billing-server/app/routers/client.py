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
        logger.warning(f"AUDIT DIAGNOSTIC: get_vpn_identity raised EntityNotFoundError for {current_account.account_id}")
        raise
    
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
