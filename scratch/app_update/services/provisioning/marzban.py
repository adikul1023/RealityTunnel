"""
marzban.py — Marzban implementation of the ProvisioningProvider interface.
Communicates with Marzban via async HTTP, implements backoff retries for transient failures,
and adheres to a strict zero-secret logging policy.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine
import httpx

from app.config import settings
from app.services.exceptions import (
    ProvisioningProviderError,
    ProvisioningConflictError,
    ProvisioningUnavailableError,
    ProvisioningTimeoutError,
)
from app.services.provisioning.provider import ProvisioningProvider, ProvisionedUserDTO, RealityConfigDTO

logger = logging.getLogger(__name__)


class MarzbanProvisioningProvider(ProvisioningProvider):
    """
    Marzban integration provider.
    Translates protocol calls into REST requests against Marzban API endpoints.
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
        self._cached_reality_config: RealityConfigDTO | None = None
        self._cached_reality_time: float = 0.0

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
        Execute an HTTP request against Marzban with exponential backoff retries
        for transient network errors and 50x server errors.
        Sanitizes all log outputs to guarantee zero secret leakage.
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

                # Return immediately if status is expected or 404 (handled by caller)
                if response.status_code in expected_statuses or response.status_code == 404:
                    return response

                # 409 Conflict
                if response.status_code == 409:
                    logger.warning(
                        "Marzban conflict error for path=%s status=%d",
                        path,
                        response.status_code,
                    )
                    raise ProvisioningConflictError(f"Resource conflict in Marzban at {path}")

                # 400 Bad Request might indicate duplicate user or validation error
                if response.status_code == 400:
                    logger.warning(
                        "Marzban bad request for path=%s status=%d",
                        path,
                        response.status_code,
                    )
                    raise ProvisioningConflictError(
                        f"Bad request or resource conflict in Marzban at {path}"
                    )

                # Retry on 502, 503, 504
                if response.status_code in (502, 503, 504):
                    logger.warning(
                        "Transient server error from Marzban attempt=%d/%d status=%d",
                        attempt,
                        self.max_retries,
                        response.status_code,
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                        continue
                    raise ProvisioningUnavailableError(
                        f"Marzban service unavailable (HTTP {response.status_code})"
                    )

                # Any other error status
                logger.error(
                    "Marzban API request failed path=%s status=%d",
                    path,
                    response.status_code,
                )
                raise ProvisioningProviderError(
                    f"Marzban API error HTTP {response.status_code} on {path}"
                )

            except httpx.TimeoutException as exc:
                last_exception = exc
                logger.warning(
                    "Marzban request timeout attempt=%d/%d path=%s",
                    attempt,
                    self.max_retries,
                    path,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise ProvisioningTimeoutError(
                    f"Marzban API request timed out on {path}"
                ) from exc

            except (httpx.NetworkError, httpx.ConnectError) as exc:
                last_exception = exc
                logger.warning(
                    "Marzban connection error attempt=%d/%d path=%s",
                    attempt,
                    self.max_retries,
                    path,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise ProvisioningUnavailableError(
        logger.info("Creating remote user in Marzban username=%s", username)
        response = await self._request_with_retry("POST", path, json=payload, expected_statuses=(200, 201))
        if response.status_code == 404:
            raise ProvisioningProviderError(f"Marzban endpoint not found: {path}")

        try:
            data = response.json()
            return self._parse_user_dto(data, username)
        except Exception as exc:
            raise ProvisioningProviderError("Failed to parse JSON response from Marzban create_user") from exc

    async def update_user(
        self,
        username: str,
        data_limit: int | None = None,
        expire_at: int | None = None,
        status: str | None = None,
    ) -> ProvisionedUserDTO:
        """Update existing user in Marzban."""
        path = settings.marzban_update_user_path.format(username=username)
        payload: dict[str, Any] = {
            "proxies": {"vless": {}},
            "inbounds": {"vless": ["VLESS TCP REALITY"]}
        }
        if data_limit is not None:
            payload["data_limit"] = data_limit
        if expire_at is not None:
            payload["expire"] = expire_at
        if status is not None:
            payload["status"] = status

        logger.info("Updating remote user in Marzban username=%s", username)
        response = await self._request_with_retry("PUT", path, json=payload, expected_statuses=(200,))
        if response.status_code == 404:
            raise ProvisioningProviderError(f"Remote user not found in Marzban: {username}")

        try:
            data = response.json()
            return self._parse_user_dto(data, username)
        except Exception as exc:
            raise ProvisioningProviderError("Failed to parse JSON response from Marzban update_user") from exc

    async def suspend_user(self, username: str) -> ProvisionedUserDTO:
        """Suspend user by setting status to disabled in Marzban."""
        logger.info("Suspending remote user in Marzban username=%s", username)
        return await self.update_user(username, status="disabled")

    async def unsuspend_user(self, username: str) -> ProvisionedUserDTO:
        """Reactivate user by setting status to active in Marzban."""
        logger.info("Unsuspending remote user in Marzban username=%s", username)
        return await self.update_user(username, status="active")

    async def delete_user(self, username: str) -> bool:
        """Delete user in Marzban."""
        path = settings.marzban_delete_user_path.format(username=username)
        logger.info("Deleting remote user in Marzban username=%s", username)
        response = await self._request_with_retry("DELETE", path, expected_statuses=(200, 204))
        if response.status_code == 404:
            # If user already doesn't exist, delete is idempotent and safe
            logger.info("Remote user already deleted or not found in Marzban username=%s", username)
            return True
        return True

    async def get_user(self, username: str) -> ProvisionedUserDTO | None:
        """Fetch user status from Marzban."""
        path = settings.marzban_get_user_path.format(username=username)
        response = await self._request_with_retry("GET", path, expected_statuses=(200,))
        if response.status_code == 404:
            return None

        try:
            data = response.json()
            return self._parse_user_dto(data, username)
        except Exception as exc:
            raise ProvisioningProviderError("Failed to parse JSON response from Marzban get_user") from exc

    async def sync_user(self, username: str) -> ProvisionedUserDTO:
        """Synchronize user state from Marzban."""
        user_dto = await self.get_user(username)
        if not user_dto:
            raise ProvisioningProviderError(f"Cannot sync user: remote user '{username}' not found in Marzban")
        return user_dto

    async def reset_user_credentials(self, username: str) -> ProvisionedUserDTO:
        """Reset/rotate user credentials (UUID and VLESS links) in Marzban."""
        path = settings.marzban_reset_user_path.format(username=username)
        logger.info("Resetting remote user credentials in Marzban username=%s", username)
        response = await self._request_with_retry("POST", path, expected_statuses=(200,))
        if response.status_code == 404:
            raise ProvisioningProviderError(f"Remote user not found in Marzban: {username}")

        try:
            data = response.json()
            return self._parse_user_dto(data, username)
        except Exception as exc:
            raise ProvisioningProviderError("Failed to parse JSON response from Marzban reset_user_credentials") from exc

    async def health_check(self) -> bool:
        """Check connection health against Marzban system stats endpoint."""
        path = settings.marzban_system_stats_path
        try:
            response = await self._request_with_retry("GET", path, expected_statuses=(200,))
            return response.status_code == 200
        except Exception:
            logger.warning("Marzban health check failed")
            return False

    async def get_reality_config(self) -> RealityConfigDTO:
        import time
        now = time.time()
        if self._cached_reality_config and (now - self._cached_reality_time) < 300:
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
                inbound_tag=target_inbound.get("tag", "VLESS TCP REALITY")
            )
            
            self._cached_reality_config = config
            self._cached_reality_time = now
            return config
        except ProvisioningProviderError:
            raise
        except Exception as exc:
            raise ProvisioningProviderError("Failed to fetch REALITY configuration from Marzban") from exc

