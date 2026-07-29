
import asyncio
from app.services.provisioning.marzban import MarzbanProvisioningProvider
from app.config import get_settings
from app.models.subscription_plan import QUARTERLY

async def main():
    settings = get_settings()
    provider = MarzbanProvisioningProvider(settings)
    await provider.initialize()
    users = await provider.get_users()
    for user in users:
        print(f'Found user: {user.username} {user.data_limit}')
        if user.username == '0ea43cc5-8a2b-426c-843e-79774659b85c':
            print(f'Updating user {user.username} with QUARTERLY data limit: {QUARTERLY.data_limit_bytes}')
            await provider.update_user(user.username, data_limit=QUARTERLY.data_limit_bytes)
            print('Successfully updated!')
            break

asyncio.run(main())

