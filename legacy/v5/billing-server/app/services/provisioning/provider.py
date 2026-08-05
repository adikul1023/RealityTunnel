"""
provider.py — Abstract interface and DTOs for VPN provisioning providers.
Isolates all Marzban/Xray/WireGuard specifics behind a clean, protocol-agnostic domain contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time

# Re-export the new interface so importers of provider.py get IVpnProvider too
from app.services.provisioning.interfaces import IVpnProvider  # noqa: F401


@dataclass
class ProvisionedUserDTO:
    """
    Data Transfer Object representing a provisioned VPN user in the remote provider.
    
    IMPORTANT ARCHITECTURAL INVARIANT:
    The `links` attribute may contain VLESS URIs or sensitive connection strings.
    These links MUST NEVER be written to logs, console output, or stored in plaintext database columns.
    """
    remote_user_id: str
    status: str
    data_limit: int | None = None
    data_used: int | None = None
    expire_at: int | None = None
    uuid: str | None = None
    links: list[str] = field(default_factory=list)
    last_ip: str | None = None


@dataclass
class RealityConfigDTO:
    """
    Unified authoritative REALITY inbound configuration fetched from the VPN edge.
    Guarantees every client receives identical runtime configuration.
    """
    server_host: str
    server_port: int
    public_key: str
    short_id: str
    sni: str
    inbound_tag: str
    fetched_at: float = field(default_factory=time.time)


class ProvisioningProvider(ABC):
    """
    Abstract base class for VPN provisioning providers.
    All external provider implementations must conform to this async interface
    and translate their specific network/protocol exceptions into domain exceptions.
    """

    @abstractmethod
    async def create_user(
        self,
        username: str,
        data_limit: int | None = None,
        expire_at: int | None = None,
    ) -> ProvisionedUserDTO:
        """Create a new VPN user in the remote provider."""
        pass

    @abstractmethod
    async def update_user(
        self,
        username: str,
        data_limit: int | None = None,
        expire_at: int | None = None,
        status: str | None = None,
    ) -> ProvisionedUserDTO:
        """Update limits, expiration, or status for an existing VPN user."""
        pass

    @abstractmethod
    async def suspend_user(self, username: str) -> ProvisionedUserDTO:
        """Suspend/disable VPN access for a user."""
        pass

    @abstractmethod
    async def unsuspend_user(self, username: str) -> ProvisionedUserDTO:
        """Reactivate/enable VPN access for a previously suspended user."""
        pass

    @abstractmethod
    async def delete_user(self, username: str) -> bool:
        """Permanently delete a user from the remote VPN provider."""
        pass

    @abstractmethod
    async def get_user(self, username: str) -> ProvisionedUserDTO | None:
        """Fetch current status and usage metrics for a remote VPN user."""
        pass

    @abstractmethod
    async def sync_user(self, username: str) -> ProvisionedUserDTO:
        """Synchronize and return the latest state of a remote VPN user."""
        pass

    @abstractmethod
    async def reset_user_credentials(self, username: str) -> ProvisionedUserDTO:
        """Reset/rotate credentials (UUID, links) for an existing remote VPN user."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check connection health and readiness of the remote provisioning service."""
        pass

    @abstractmethod
    async def get_reality_config(self) -> RealityConfigDTO:
        """Fetch unified REALITY configuration from the provider."""
        pass

