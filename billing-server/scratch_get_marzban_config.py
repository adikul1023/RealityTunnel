import asyncio
from app.config import settings
from app.services.provisioning.marzban import MarzbanProvisioningProvider

async def main():
    provider = MarzbanProvisioningProvider()
    print("Base URL configured as:", provider.base_url)
    
    # Hit Marzban API directly
    response = await provider._request_with_retry("GET", "/api/core/config", expected_statuses=(200,))
    print(response.text)

if __name__ == "__main__":
    asyncio.run(main())
