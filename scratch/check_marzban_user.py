import asyncio
from app.services.provisioning.marzban import MarzbanProvisioningProvider

async def check():
    provider = MarzbanProvisioningProvider()
    user = await provider.get_user("ST-1RY7-7X1F")
    print(user)

asyncio.run(check())
