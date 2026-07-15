import asyncio
from typing import Any
from app.config import settings
import httpx

async def get_user_and_update():
    path = settings.marzban_update_user_path.format(username="user_st-1ry7-7x1f")
    payload: dict[str, Any] = {
        "proxies": {"vless": {}},
        "inbounds": {"vless": ["VLESS TCP REALITY"]}
    }
    
    base_url = (settings.marzban_rpc_url or getattr(settings, 'marzban_base_url', '')).rstrip('/')
    url = f"{base_url}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {settings.marzban_api_token.get_secret_value()}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=10, verify=False) as client:
        response = await client.request("PUT", url, headers=headers, json=payload)
        print("Status:", response.status_code)
        print("Text:", response.text)

asyncio.run(get_user_and_update())
