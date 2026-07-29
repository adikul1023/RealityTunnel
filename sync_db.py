import asyncio
from app.database import AsyncSessionLocal
from app.services.provisioning.repo import ProvisioningRepository
from app.services.provisioning.marzban import MarzbanProvisioningProvider

async def main():
    print("Starting sync...")
    provider = MarzbanProvisioningProvider()
    async with AsyncSessionLocal() as session:
        repo = ProvisioningRepository(session)
        profiles = await repo.get_all_active()
        print(f"Found {len(profiles)} active profiles")
        for p in profiles:
            try:
                print(f"Fixing {p.remote_user_id}...")
                await provider.update_user(p.remote_user_id)
            except Exception as e:
                print(f"Error {p.remote_user_id}: {e}")
    print("Done sync.")

asyncio.run(main())
