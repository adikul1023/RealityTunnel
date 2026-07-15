import asyncio
from app.config import settings
import httpx

async def get_inbounds():
    base_url = (settings.marzban_rpc_url or getattr(settings, 'marzban_base_url', '')).rstrip('/')
    url = f"{base_url}/api/inbounds"
    headers = {
        "Authorization": f"Bearer {settings.marzban_api_token.get_secret_value()}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=10, verify=False) as client:
        response = await client.request("GET", url, headers=headers)
        print("Status:", response.status_code)
        print("Text:", response.text)

asyncio.run(get_inbounds())
