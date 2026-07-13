import asyncio
import os
import sys

# Ensure app module can be found
sys.path.insert(0, r"d:\My projects\VPN\OverREALITY\billing-server")

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.account import Account
from app.models.subscription import Subscription
from app.models.provisioning import ProvisioningProfile
from app.models.subscription import SubscriptionLifecycleStatus
from app.models.provisioning import ProvisioningState
from app.services.provisioning import ProvisioningService
from app.services.provisioning.marzban import MarzbanProvisioningProvider
from app.repositories.provisioning_repository import ProvisioningRepository

async def main():
    print(f"Marzban base: {settings.marzban_base_url}")
    
    provider = MarzbanProvisioningProvider()

    account_id = "ST-HTI8-N1ND"
    master_token = "TEST_TOKEN_HASH"

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(Account).where(Account.account_id == account_id))
        existing = result.scalar_one_or_none()
        if not existing:
            print("Creating account...")
            acc = Account(account_id=account_id, master_token_hash=master_token, plan_id="standard")
            session.add(acc)
            await session.flush()
            
            sub = Subscription(
                id="SUB-1234",
                account_id=acc.id,
                plan_id="standard",
                status=SubscriptionLifecycleStatus.ACTIVE
            )
            session.add(sub)
            await session.commit()
            existing = acc

        db_account_id = existing.id

    # Call the Provisioning Service to provision the subscription
    async with AsyncSessionLocal() as session:
        print("Running ProvisioningService.provision_subscription...")
        service = ProvisioningService(session, provider)
        prof = await service.provision_subscription(db_account_id, "standard")
        print(f"Provisioned successfully -> vpn_uuid: {prof.vpn_uuid}, remote_user_id: {prof.remote_user_id}")

        print("Running ProvisioningService.get_vpn_identity...")
        vpn_identity = await service.get_vpn_identity(db_account_id)
        print(f"VPN Identity: {vpn_identity}")

asyncio.run(main())
