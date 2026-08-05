"""
credential_models.py — Transport DTOs for Phase 2.4 VPN Credential REST API.
Exposes only safe client configuration properties and canonical connection parameters.
Never exposes API tokens, Marzban credentials, internal IDs, database UUIDs, or provider secrets.
"""
from typing import Any
from pydantic import BaseModel, Field


class CredentialResponse(BaseModel):
    """
    Complete VPN credential transport model.
    Contains canonical parameters and generated client config blob.
    """
    server_hostname: str = Field(..., description="VPN gateway hostname or IP")
    port: int = Field(..., description="VPN service port")
    protocol: str = Field(..., description="VPN protocol (e.g., vless)")
    transport: str = Field(..., description="Network transport layer (e.g., tcp)")
    security: str = Field(..., description="Security protocol (e.g., reality)")
    uuid: str = Field(..., description="Client authentication UUID")
    public_key: str = Field(..., description="REALITY public key")
    short_id: str = Field(..., description="REALITY short ID")
    sni: str = Field(..., description="Server Name Indication domain")
    client_config: dict[str, Any] = Field(..., description="Generated sing-box JSON configuration blob")


class VlessResponse(BaseModel):
    """
    Transport model for canonical VLESS URI string.
    """
    vless_uri: str = Field(..., description="Complete VLESS reality URI link")


class SingboxResponse(BaseModel):
    """
    Transport model for dynamic sing-box JSON configuration.
    """
    config: dict[str, Any] = Field(..., description="sing-box outbound configuration dictionary")


class ClashResponse(BaseModel):
    """
    Transport model for Clash configuration placeholder.
    """
    config: dict[str, Any] = Field(..., description="Clash configuration or placeholder dictionary")


class CredentialStatusResponse(BaseModel):
    """
    Transport model for revocation and restoration action status.
    """
    status: str = Field(..., description="Status of credential action (revoked or restored)")
