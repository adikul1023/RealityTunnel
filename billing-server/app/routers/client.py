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
    server_ip: str = Field(..., description="VPN Server IP")
    public_key: str = Field(..., description="REALITY Public Key")
    sni: str = Field(..., description="Server Name Indication")
    dns: str | None = Field(None, description="DNS Server IP")


class LicenseBlobDto(BaseModel):
    payload: str = Field(..., description="Base64 encoded license payload")
    signature: str = Field(..., description="Ed25519 signature of the payload")


class ClientConfigResponse(BaseModel):
    vpn_profile: VpnProfileDto
    license_blob: LicenseBlobDto


@router.get(
    "/config",
    summary="Fetch VPN configuration and offline license blob",
    response_model=ClientConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def get_client_config(
    current_account: Account = Depends(get_current_account),
) -> ClientConfigResponse:
    """
    Returns the VPN profile (for the client's VPN engine) and an offline License Blob 
    (for offline authorization when Oracle is unreachable).
    """
    # TODO: In a real implementation, these values would come from the provisioning system
    # and the License Blob would be signed by the backend's Ed25519 private key.
    # For Phase 8.3 integration testing, we return stubbed valid data.
    
    return ClientConfigResponse(
        vpn_profile=VpnProfileDto(
            uuid="b8398dbd-a7b2-4d24-87dc-7bbf1cf033de",
            server_ip="144.24.153.180", # Example Contabo IP
            public_key="some-reality-public-key",
            sni="www.microsoft.com",
            dns="1.1.1.1"
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
