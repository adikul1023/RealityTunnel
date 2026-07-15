import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any
from app.database import AsyncSessionLocal
from app.services.provisioning.service import ProvisioningService
from app.services.provisioning.marzban import MarzbanProvisioningProvider
from app.services.provisioning.provider import ProvisionedUserDTO
from app.repositories.account_repository import AccountRepository
from app.services.credential_service import CredentialService
from app.services.exceptions import ProvisioningConflictError, ProvisioningProviderError
from app.config import settings
import httpx

class PatchedMarzbanProvider(MarzbanProvisioningProvider):
    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        expected_statuses: tuple[int, ...] = (200, 201),
    ) -> httpx.Response:
        base_url = (settings.marzban_rpc_url or getattr(settings, 'marzban_base_url', '')).rstrip('/')
        url = f"{base_url}/{path.lstrip('/')}"
        
        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            response = await client.request(method, url, headers=self._headers, json=json)
            if response.status_code in expected_statuses:
                return response
            if response.status_code == 409:
                raise ProvisioningConflictError("Conflict")
            raise ProvisioningProviderError(f"HTTP {response.status_code}")

async def provision():
    async with AsyncSessionLocal() as session:
        account_repo = AccountRepository(session)
        provider = PatchedMarzbanProvider()
        prov_svc = ProvisioningService(session, provider, None)
        cred_svc = CredentialService(session, prov_svc)
        prov_svc.credential_service = cred_svc
        
        account_id_str = "ST-1RY7-7X1F"
        account = await account_repo.get_by_account_id(account_id_str)
        if not account:
            print("Account not found")
            return
            
        expires = datetime.now(timezone.utc) + timedelta(days=3650)
        profile = await prov_svc.provision_subscription(account.id, "free", expires)
        print("Provisioned:", profile.remote_user_id, "UUID:", profile.vpn_uuid)

asyncio.run(provision())
