"""
credential_service.py — VPN Credential Lifecycle & Client Configuration Delivery Service (Phase 2.4).
Responsible for securely exposing VPN credentials to authenticated users after provisioning.
Never communicates with Marzban directly; consumes ProvisioningService exclusively.
Enforces zero-secret logging and generates client configuration blobs on demand.
"""
from __future__ import annotations

import logging
import urllib.parse
import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EntityNotFoundError
from app.models import ProvisioningState, ProvisioningProfile
from app.services.provisioning.provider import ProvisionedUserDTO
from app.services.provisioning.service import ProvisioningService
from app.services.exceptions import (
    CredentialServiceError,
    CredentialNotFoundError,
    CredentialAlreadyRevokedError,
    CredentialAlreadyActiveError,
    CredentialRotationFailedError,
    ProvisioningServiceError,
    ProvisioningConflictError,
)

logger = logging.getLogger(__name__)


class CredentialService:
    """
    Domain service for VPN credential lifecycle management.
    Retrieves canonical provisioning profile from ProvisioningService and dynamically generates
    VLESS URIs, sing-box configurations, and Clash placeholders on demand without storing
    configuration blobs in database columns.
    """

    def __init__(self, session: AsyncSession, provisioning_service: ProvisioningService) -> None:
        self.session = session
        self.provisioning_service = provisioning_service

    def _extract_vless_uri(self, links: list[str]) -> str:
        """Find and return the VLESS URI from provider link list."""
        for link in links:
            if link.startswith("vless://"):
                return link
        raise CredentialNotFoundError("No VLESS URI found in remote provisioning profile.")

    def _parse_vless_uri(self, uri: str, remote_user_id: str) -> dict[str, Any]:
        """
        Parse a canonical VLESS Reality URI into transport components.
        Format: vless://uuid@hostname:port?type=tcp&security=reality&pbk=pubkey&sni=sni&sid=shortid#tag
        """
        try:
            parsed = urllib.parse.urlparse(uri)
            client_uuid = parsed.username or remote_user_id
            hostname = parsed.hostname or "vpn.realitytunnel.com"
            port = parsed.port or 443

            query_params = urllib.parse.parse_qs(parsed.query)
            transport = query_params.get("type", ["tcp"])[0]
            security = query_params.get("security", ["reality"])[0]
            public_key = query_params.get("pbk", [""])[0]
            short_id = query_params.get("sid", [""])[0]
            sni = query_params.get("sni", [hostname])[0]

            return {
                "server_hostname": hostname,
                "port": port,
                "protocol": "vless",
                "transport": transport,
                "security": security,
                "uuid": client_uuid,
                "public_key": public_key,
                "short_id": short_id,
                "sni": sni,
                "vless_uri": uri,
            }
        except Exception as exc:
            logger.error("Failed to parse VLESS URI structure")
            raise CredentialServiceError("Malformed VLESS URI in provisioning profile") from exc

    def _generate_singbox_config(self, meta: dict[str, Any]) -> dict[str, Any]:
        """
        Generate a canonical sing-box 1.8+ outbound configuration dictionary on demand.
        Never stored in database.
        """
        return {
            "log": {"level": "info"},
            "outbounds": [
                {
                    "type": "vless",
                    "tag": "proxy",
                    "server": meta["server_hostname"],
                    "server_port": meta["port"],
                    "uuid": meta["uuid"],
                    "flow": "xtls-rprx-vision",
                    "network": meta["transport"],
                    "tls": {
                        "enabled": True,
                        "server_name": meta["sni"],
                        "utls": {"enabled": True, "fingerprint": "chrome"},
                        "reality": {
                            "enabled": True,
                            "public_key": meta["public_key"],
                            "short_id": meta["short_id"],
                        },
                    },
                },
                {"type": "direct", "tag": "direct"},
            ],
        }

    def _generate_clash_config(self, meta: dict[str, Any]) -> dict[str, Any]:
        """
        Generate placeholder configuration for Clash (REALITY unsupported in standard Clash).
        """
        return {
            "status": "unsupported",
            "message": "Clash REALITY configuration is currently unsupported. Please use sing-box or VLESS URI.",
            "protocol": "vless-reality",
            "server": meta["server_hostname"],
            "port": meta["port"],
        }

    def _build_credential_payload(
        self,
        profile: ProvisioningProfile,
        user_dto: ProvisionedUserDTO,
    ) -> dict[str, Any]:
        """Build the full credential dictionary with generated client configs."""
        vless_uri = self._extract_vless_uri(user_dto.links)
        meta = self._parse_vless_uri(vless_uri, profile.remote_user_id)

        singbox_config = self._generate_singbox_config(meta)
        clash_config = self._generate_clash_config(meta)

        return {
            "server_hostname": meta["server_hostname"],
            "port": meta["port"],
            "protocol": meta["protocol"],
            "transport": meta["transport"],
            "security": meta["security"],
            "uuid": meta["uuid"],
            "public_key": meta["public_key"],
            "short_id": meta["short_id"],
            "sni": meta["sni"],
            "client_config": singbox_config,
            "vless_uri": meta["vless_uri"],
            "singbox_config": singbox_config,
            "clash_config": clash_config,
        }

    async def get_credentials(self, account_id: uuid.UUID) -> dict[str, Any]:
        """
        Retrieve active VPN profile and client configurations for an account.
        Idempotent: repeated retrievals return the current active profile without regenerating.
        """
        try:
            profile, user_dto = await self.provisioning_service.get_provisioned_user(account_id)
        except EntityNotFoundError as exc:
            raise CredentialNotFoundError(f"No provisioning profile found for account {account_id}") from exc
        except Exception as exc:
            raise CredentialServiceError(str(exc)) from exc

        if profile.provisioning_state == ProvisioningState.TERMINATED:
            raise CredentialNotFoundError(f"Provisioning profile for account {account_id} is terminated")

        if profile.provisioning_state == ProvisioningState.SUSPENDED or user_dto.status.lower() in ("disabled", "suspended", "inactive"):
            raise CredentialAlreadyRevokedError(f"Provisioning profile for account {account_id} is revoked or suspended")

        logger.info("Retrieved active credentials for account_id=%s", account_id)
        return self._build_credential_payload(profile, user_dto)

    async def get_vless_uri(self, account_id: uuid.UUID) -> str:
        """Retrieve VLESS URI for an account."""
        data = await self.get_credentials(account_id)
        return str(data["vless_uri"])

    async def get_singbox_config(self, account_id: uuid.UUID) -> dict[str, Any]:
        """Retrieve sing-box JSON configuration for an account."""
        data = await self.get_credentials(account_id)
        return dict(data["singbox_config"])

    async def get_clash_config(self, account_id: uuid.UUID) -> dict[str, Any]:
        """Retrieve Clash placeholder configuration for an account."""
        data = await self.get_credentials(account_id)
        return dict(data["clash_config"])

    async def regenerate_credentials(self, account_id: uuid.UUID) -> dict[str, Any]:
        """
        Rotate and regenerate credentials for an account.
        Acquires row lock, invalidates previous credential, and synchronizes with provider.
        """
        try:
            profile, user_dto = await self.provisioning_service.rotate_user_credentials(account_id)
            logger.info("Successfully rotated credentials for account_id=%s", account_id)
            return self._build_credential_payload(profile, user_dto)
        except EntityNotFoundError as exc:
            raise CredentialNotFoundError(f"No provisioning profile found for account {account_id}") from exc
        except Exception as exc:
            logger.error("Failed credential rotation for account_id=%s", account_id)
            raise CredentialRotationFailedError(f"Credential rotation failed: {str(exc)}") from exc

    async def revoke_credentials(self, account_id: uuid.UUID) -> None:
        """
        Revoke active credentials by suspending the remote provisioning profile.
        Idempotency / State Check: raises CredentialAlreadyRevokedError if already suspended.
        """
        profile = await self.provisioning_service.provisioning_repo.get_by_account_id(account_id, for_update=True)
        if not profile or profile.provisioning_state == ProvisioningState.TERMINATED:
            raise CredentialNotFoundError(f"No active provisioning profile found for account {account_id}")

        if profile.provisioning_state == ProvisioningState.SUSPENDED:
            raise CredentialAlreadyRevokedError(f"Credentials for account {account_id} are already revoked/suspended")

        try:
            await self.provisioning_service.suspend_subscription(account_id)
            logger.info("Successfully revoked credentials for account_id=%s", account_id)
        except Exception as exc:
            raise CredentialServiceError(f"Failed to revoke credentials: {str(exc)}") from exc

    async def restore_credentials(self, account_id: uuid.UUID) -> None:
        """
        Restore previously revoked credentials by reactivating the remote provisioning profile.
        Idempotency / State Check: raises CredentialAlreadyActiveError if already active.
        """
        profile = await self.provisioning_service.provisioning_repo.get_by_account_id(account_id, for_update=True)
        if not profile or profile.provisioning_state == ProvisioningState.TERMINATED:
            raise CredentialNotFoundError(f"No provisioning profile found for account {account_id}")

        if profile.provisioning_state == ProvisioningState.ACTIVE:
            raise CredentialAlreadyActiveError(f"Credentials for account {account_id} are already active")

        try:
            await self.provisioning_service.reactivate_subscription(account_id)
            logger.info("Successfully restored credentials for account_id=%s", account_id)
        except Exception as exc:
            raise CredentialServiceError(f"Failed to restore credentials: {str(exc)}") from exc
