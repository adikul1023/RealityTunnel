import asyncio
import sys

from app.db.session import async_session_maker
from app.services.provisioning.repo import ProvisioningRepository
from app.services.provisioning.marzban import MarzbanProvisioningProvider
from app.config import settings

async def main():
    provider = MarzbanProvisioningProvider()
    async with async_session_maker() as session:
        repo = ProvisioningRepository(session)
        profiles = await repo.get_all_active()
        print(f"Found {len(profiles)} active profiles")
        for p in profiles:
            try:
                print(f"Fixing {p.remote_user_id}...")
                await provider.update_user(p.remote_user_id)
            except Exception as e:
                print(f"Error {p.remote_user_id}: {e}")

asyncio.run(main())
