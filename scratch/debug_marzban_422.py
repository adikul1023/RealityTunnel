import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any
from app.database import AsyncSessionLocal
from app.services.provisioning.service import ProvisioningService
from app.services.provisioning.marzban import MarzbanProvisioningProvider
from app.services.provisioning.provider import ProvisionedUserDTO
from app.repositories.account_repository import AccountRepository
from app.services.credential_service import CredentialService
from app.config import settings
import httpx

class PatchedMarzbanProvider(MarzbanProvisioningProvider):
    async def create_user(self, username: str, data_limit: int | None = None, expire_at: int | None = None) -> ProvisionedUserDTO:
        path = settings.marzban_create_user_path
        payload: dict[str, Any] = {
            "username": username, 
            "status": "active",
            "proxies": {"vless": {}},
            "inbounds": {"vless": ["VLESS_REALITY"]}
        }
        if data_limit is not None:
            payload["data_limit"] = data_limit
        if expire_at is not None:
            payload["expire"] = expire_at
        
        try:
            url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                response = await client.request("POST", url, headers=self._headers, json=payload)
                print("Status:", response.status_code)
                print("Text:", response.text)
                return None
        except Exception as e:
            print("Exception:", e)

async def provision():
    async with AsyncSessionLocal() as session:
        account_repo = AccountRepository(session)
        provider = PatchedMarzbanProvider()
        
        account_id_str = "ST-1RY7-7X1F"
        account = await account_repo.get_by_account_id(account_id_str)
        if not account:
            print("Account not found")
            return
            
        expires = datetime.now(timezone.utc) + timedelta(days=3650)
        await provider.create_user(account.marzban_username or str(account.id), None, None)

asyncio.run(provision())
