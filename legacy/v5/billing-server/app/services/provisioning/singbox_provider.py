import asyncio
import logging
from typing import Any, Dict

import httpx

from app.config import settings
from app.services.exceptions import (
    ProvisioningConflictError,
    ProvisioningTimeoutError,
    ProvisioningUnavailableError,
    ProvisioningProviderError,
)
from app.services.provisioning.interfaces import IVpnProvider, RealityConfigDTO

logger = logging.getLogger(__name__)

class SingBoxProvider(IVpnProvider):
    """
    Marzban integration provider mapped to the IVpnProvider interface.
    Translates IVpnProvider calls into REST requests against Marzban API endpoints.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.marzban_rpc_url or settings.marzban_base_url).rstrip("/")
        self.api_token = api_token if api_token is not None else settings.marzban_api_token.get_secret_value()
        self.timeout = timeout_seconds if timeout_seconds is not None else settings.marzban_timeout_seconds
        self.max_retries = max_retries if max_retries is not None else settings.marzban_max_retries
        self._external_client = client

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        expected_statuses: tuple[int, ...] = (200, 201),
    ) -> httpx.Response:
        """
        Execute an HTTP request against Marzban with exponential backoff retries.
        """
        url = f"{self.base_url}{path}"
        last_exception: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self._external_client:
                    response = await self._external_client.request(
                        method,
                        url,
                        headers=self._headers,
                        json=json,
                        timeout=self.timeout,
                    )
                else:
                    async with httpx.AsyncClient(
                        timeout=self.timeout,
                        verify=False,
                    ) as client:
                        response = await client.request(
                            method,
                            url,
                            headers=self._headers,
                            json=json,
                        )

                if response.status_code in expected_statuses or response.status_code == 404:
                    return response

                if response.status_code == 409:
                    raise ProvisioningConflictError(f"Resource conflict in Marzban at {path}")

                if response.status_code == 400:
                    raise ProvisioningConflictError(f"Bad request or resource conflict in Marzban at {path}")

                if response.status_code in (502, 503, 504):
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                        continue
                    raise ProvisioningUnavailableError(f"Marzban service unavailable (HTTP {response.status_code})")

                raise ProvisioningProviderError(f"Marzban API error HTTP {response.status_code} on {path}")

            except httpx.TimeoutException as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise ProvisioningTimeoutError(f"Marzban API request timed out on {path}") from exc

            except (httpx.NetworkError, httpx.ConnectError) as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise ProvisioningUnavailableError(f"Marzban API unreachable on {path}") from exc
                
        raise ProvisioningProviderError("Max retries exceeded") from last_exception

    async def ensure_provisioned(
        self,
        account: Any,
        remote_user_id: str,
        data_limit: int | None = None,
        expire_at: int | None = None,
    ) -> Dict[str, Any]:
        path = f"/api/user/{remote_user_id}"
        payload = {
            "proxies": {"vless": {}},
            "inbounds": {"vless": ["VLESS TCP REALITY"]}
        }
        if data_limit is not None:
            payload["data_limit"] = data_limit
        if expire_at is not None:
            payload["expire"] = expire_at

        response = await self._request_with_retry("PUT", path, json=payload, expected_statuses=(200,))
        if response.status_code == 404:
            payload["username"] = remote_user_id
            payload["status"] = "active"
            payload["data_limit_reset_strategy"] = "no_reset"
            payload["proxies"]["vless"]["flow"] = ""
            create_path = "/api/user"
            response = await self._request_with_retry("POST", create_path, json=payload, expected_statuses=(200, 201))
            if response.status_code == 404:
                raise ProvisioningProviderError(f"Marzban endpoint not found: {create_path}")

        try:
            return response.json()
        except Exception as exc:
            raise ProvisioningProviderError("Failed to parse JSON response from ensure_provisioned") from exc

    async def sync(self, account: Any, remote_user_id: str) -> Dict[str, Any]:
        path = f"/api/user/{remote_user_id}"
        response = await self._request_with_retry("GET", path, expected_statuses=(200,))
        if response.status_code == 404:
            raise ProvisioningProviderError(f"User not found: {remote_user_id}")
        
        try:
            return response.json()
        except Exception as exc:
            raise ProvisioningProviderError("Failed to parse JSON response from sync") from exc

    async def rotate_credentials(self, account: Any, remote_user_id: str) -> Dict[str, Any]:
        path = f"/api/user/{remote_user_id}/reset"
        response = await self._request_with_retry("POST", path, expected_statuses=(200,))
        if response.status_code == 404:
            raise ProvisioningProviderError(f"User not found: {remote_user_id}")
        
        try:
            return response.json()
        except Exception as exc:
            raise ProvisioningProviderError("Failed to parse JSON response from rotate_credentials") from exc

    async def suspend(self, account: Any, remote_user_id: str) -> None:
        path = f"/api/user/{remote_user_id}"
        payload = {"status": "disabled"}
        response = await self._request_with_retry("PUT", path, json=payload, expected_statuses=(200,))
        if response.status_code == 404:
            raise ProvisioningProviderError(f"User not found: {remote_user_id}")

    async def resume(self, account: Any, remote_user_id: str) -> None:
        path = f"/api/user/{remote_user_id}"
        payload = {"status": "active"}
        response = await self._request_with_retry("PUT", path, json=payload, expected_statuses=(200,))
        if response.status_code == 404:
            raise ProvisioningProviderError(f"User not found: {remote_user_id}")

    async def revoke(self, account: Any, remote_user_id: str) -> None:
        path = f"/api/user/{remote_user_id}"
        response = await self._request_with_retry("DELETE", path, expected_statuses=(200,))
        if response.status_code == 404:
            logger.warning(f"User {remote_user_id} not found during revoke, ignoring")

    async def health_check(self) -> bool:
        try:
            response = await self._request_with_retry("GET", "/api/system", expected_statuses=(200,))
            return response.status_code == 200
        except Exception:
            return False

    async def get_reality_config(self) -> RealityConfigDTO:
        import time
        now = time.time()
        if getattr(self, '_cached_reality_config', None) and getattr(self, '_cached_reality_time', 0) and (now - self._cached_reality_time) < 300:
            return self._cached_reality_config

        path = "/api/inbounds"
        try:
            response = await self._request_with_retry("GET", path, expected_statuses=(200,))
            data = response.json()
            
            target_inbound = None
            if isinstance(data, dict) and "vless" in data:
                inbounds = data["vless"]
                target_inbound = next((ib for ib in inbounds if ib.get("tag") == "VLESS TCP REALITY"), None)
            
            if not target_inbound:
                raise ProvisioningProviderError("VLESS TCP REALITY inbound not found in Marzban configuration")

            stream_settings = target_inbound.get("stream_settings", {})
            reality_settings = stream_settings.get("reality_settings", {})
            server_names = reality_settings.get("server_names", [""])
            short_ids = reality_settings.get("short_ids", [""])

            config = RealityConfigDTO(
                server_host=settings.vpn_server_ip,
                server_port=target_inbound.get("port", 443),
                public_key=reality_settings.get("public_key", ""),
                short_id=short_ids[0] if short_ids else "",
                sni=server_names[0] if server_names else "",
                inbound_tag=target_inbound.get("tag", "")
            )
            self._cached_reality_config = config
            self._cached_reality_time = now
            return config
        except Exception as exc:
            raise ProvisioningProviderError("Failed to fetch REALITY config from Marzban") from exc

    # ── ProvisioningService adapter methods ───────────────────────────────────
    # ProvisioningService uses the old ProvisioningProvider ABC names.
    # These shims map the old names to the current IVpnProvider interface so
    # the service layer does not need to be rewritten in this phase.

    def _dto_from_dict(self, data: Dict[str, Any], remote_user_id: str) -> "ProvisionedUserDTO":
        """Convert a Marzban API response dict to a ProvisionedUserDTO."""
        from app.services.provisioning.provider import ProvisionedUserDTO
        return ProvisionedUserDTO(
            remote_user_id=data.get("username", remote_user_id),
            status=data.get("status", "unknown"),
            data_limit=data.get("data_limit"),
            data_used=data.get("used_traffic"),
            expire_at=data.get("expire"),
            links=data.get("links", []),
        )

    async def get_user(self, remote_user_id: str) -> "ProvisionedUserDTO":
        """Adapter: ProvisioningProvider.get_user() → sync()."""
        data = await self.sync(None, remote_user_id)
        return self._dto_from_dict(data, remote_user_id)

    async def sync_user(self, remote_user_id: str) -> "ProvisionedUserDTO":
        """Adapter: ProvisioningProvider.sync_user() → sync()."""
        data = await self.sync(None, remote_user_id)
        return self._dto_from_dict(data, remote_user_id)

    async def reset_user_credentials(self, remote_user_id: str) -> "ProvisionedUserDTO":
        """Adapter: ProvisioningProvider.reset_user_credentials() → rotate_credentials()."""
        data = await self.rotate_credentials(None, remote_user_id)
        return self._dto_from_dict(data, remote_user_id)

    async def create_user(
        self,
        username: str,
        data_limit: int | None = None,
        expire_at: int | None = None,
    ) -> "ProvisionedUserDTO":
        """Adapter: ProvisioningProvider.create_user() → ensure_provisioned()."""
        data = await self.ensure_provisioned(None, username, data_limit=data_limit, expire_at=expire_at)
        return self._dto_from_dict(data, username)

    async def update_user(
        self,
        username: str,
        data_limit: int | None = None,
        expire_at: int | None = None,
        status: str | None = None,
    ) -> "ProvisionedUserDTO":
        """Adapter: ProvisioningProvider.update_user() → ensure_provisioned()."""
        data = await self.ensure_provisioned(None, username, data_limit=data_limit, expire_at=expire_at)
        return self._dto_from_dict(data, username)

    async def suspend_user(self, remote_user_id: str) -> "ProvisionedUserDTO":
        """Adapter: ProvisioningProvider.suspend_user() → suspend()."""
        await self.suspend(None, remote_user_id)
        from app.services.provisioning.provider import ProvisionedUserDTO
        return ProvisionedUserDTO(remote_user_id=remote_user_id, status="disabled")

    async def unsuspend_user(self, remote_user_id: str) -> "ProvisionedUserDTO":
        """Adapter: ProvisioningProvider.unsuspend_user() → resume()."""
        await self.resume(None, remote_user_id)
        from app.services.provisioning.provider import ProvisionedUserDTO
        return ProvisionedUserDTO(remote_user_id=remote_user_id, status="active")

    async def delete_user(self, remote_user_id: str) -> bool:
        """Adapter: ProvisioningProvider.delete_user() → revoke()."""
        await self.revoke(None, remote_user_id)
        return True

