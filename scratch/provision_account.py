import asyncio
from datetime import datetime, timezone, timedelta
from app.database import AsyncSessionLocal
from app.services.provisioning.service import ProvisioningService
from app.services.provisioning.marzban import MarzbanProvisioningProvider
from app.repositories.account_repository import AccountRepository
from app.services.credential_service import CredentialService
import uuid

async def provision():
    async with AsyncSessionLocal() as session:
        account_repo = AccountRepository(session)
        
        provider = MarzbanProvisioningProvider()
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
