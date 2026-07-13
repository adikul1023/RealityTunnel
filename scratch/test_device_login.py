import asyncio
import uuid
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        res = await client.post("/api/auth/register", json={})
        account_id = res.json()["account_id"]
        master_token = res.json()["master_token"]
        device_guid = str(uuid.uuid4())
        
        login_payload = {"account_id": account_id, "master_token": master_token, "device_guid": device_guid}
        
        # 1. Login
        print("1. Logging in for the first time...")
        res = await client.post("/api/auth/login", json=login_payload)
        if res.status_code != 200:
            print("Login 1 failed:", res.text)
            return
        access_token = res.json()["access_token"]
        
        # 2. Check devices
        res = await client.get("/api/devices", headers={"Authorization": f"Bearer {access_token}"})
        print(f"2. Devices after login: {len(res.json()['devices'])}")
        
        # 3. Delete device (simulate UI Remove)
        print("3. Removing device via DELETE endpoint...")
        res = await client.delete(f"/api/devices/{device_guid}", headers={"Authorization": f"Bearer {access_token}"})
        print(f"Delete result: {res.status_code}")
        
        # 4. Check devices after delete
        res = await client.get("/api/devices", headers={"Authorization": f"Bearer {access_token}"})
        print(f"4. Devices after delete: {len(res.json()['devices'])}")
        
        # 5. Client logs in again with SAME device_guid
        print("5. Logging in again with SAME device_guid...")
        res = await client.post("/api/auth/login", json=login_payload)
        print(f"Login 2 result: {res.status_code}")
        if res.status_code == 200:
            access_token2 = res.json()["access_token"]
            res = await client.get("/api/devices", headers={"Authorization": f"Bearer {access_token2}"})
            print(f"Devices after login 2: {len(res.json()['devices'])}")

asyncio.run(main())
