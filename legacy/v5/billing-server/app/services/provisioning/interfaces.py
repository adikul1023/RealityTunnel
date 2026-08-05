from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from uuid import UUID
from dataclasses import dataclass, field
import time

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

class IVpnProvider(ABC):
    """
    Abstract interface for VPN provisioning.
    Returns dictionaries containing the necessary connection parameters and metadata.
    """

    @abstractmethod
    async def ensure_provisioned(self, account: Any, remote_user_id: str, data_limit: Optional[int] = None, expire_at: Optional[int] = None) -> Dict[str, Any]:
        """Creates or updates a VPN user configuration."""
        pass

    @abstractmethod
    async def sync(self, account: Any, remote_user_id: str) -> Dict[str, Any]:
        """Fetches current usage and status from the edge."""
        pass

    @abstractmethod
    async def rotate_credentials(self, account: Any, remote_user_id: str) -> Dict[str, Any]:
        """Rotates the underlying connection secrets (e.g. UUIDs)."""
        pass

    @abstractmethod
    async def suspend(self, account: Any, remote_user_id: str) -> None:
        """Suspends VPN access."""
        pass

    @abstractmethod
    async def resume(self, account: Any, remote_user_id: str) -> None:
        """Restores VPN access."""
        pass

    @abstractmethod
    async def revoke(self, account: Any, remote_user_id: str) -> None:
        """Permanently deletes the VPN configuration."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Checks if the edge provider is responsive."""
        pass

    @abstractmethod
    async def get_reality_config(self) -> RealityConfigDTO:
        """Fetch unified REALITY configuration from the provider."""
        pass
