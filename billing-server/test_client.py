import asyncio
import httpx
import uuid
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Account
from app.security import hash_master_token

async def main():
    plaintext = "d" * 64
    acc_id = None
    
    async with AsyncSessionLocal() as session:
        # Get the first account deterministically
        accs = (await session.execute(select(Account).order_by(Account.id))).scalars().all()
        if len(accs) > 0:
            acc = accs[0]
            acc.master_token_hash = hash_master_token(plaintext)
            await session.commit()
            acc_id = acc.account_id
            print(f"Updated account {acc_id} hash")

    if not acc_id:
        print("No accounts")
        return

    device_guid = str(uuid.uuid4())

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        res = await client.post("/api/auth/login", json={
            "account_id": acc_id,
            "master_token": plaintext,
            "device_guid": device_guid
        })
        print("LOGIN:", res.status_code, res.text)
        
        if res.status_code == 200:
            token = res.json()["access_token"]
            res2 = await client.get("/api/auth/me", headers={
                "Authorization": f"Bearer {token}"
            })
            print("ME:", res2.status_code, res2.text)
            
            res3 = await client.get("/api/client/config", headers={
                "Authorization": f"Bearer {token}",
                "x-device-id": device_guid
            })
            print("CONFIG:", res3.status_code, res3.text)

if __name__ == "__main__":
    asyncio.run(main())
