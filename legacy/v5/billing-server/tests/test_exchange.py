import pytest
from fastapi.testclient import TestClient
from app.main import app
import uuid
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Device, ExchangeToken
import hashlib
from datetime import datetime, timedelta, timezone

@pytest.mark.asyncio
async def test_exchange_flow_bug():
    client = TestClient(app)
    
    # 1. Register
    response = client.post("/api/auth/register", json={"plan_id": "quarterly", "device_type": "windows"})
    account_data = response.json()
    account_id = account_data["account_id"]
    
    # 2. First login (simulate first device)
    device_1 = str(uuid.uuid4())
    client.post("/api/auth/login", json={
        "account_id": account_id,
        "master_token": account_data["master_token"],
        "device_guid": device_1,
        "device_name": "PC 1",
        "client_version": "1.0.0",
        "client_type": "desktop"
    })
    
    # 3. Simulate Desktop Client SSO login (creating exchange token manually in DB)
    # Use a unique token per run to avoid UNIQUE constraint from prior runs
    exchange_token_str = f"test-exchange-{uuid.uuid4()}"
    token_hash = hashlib.sha256(exchange_token_str.encode("utf-8")).hexdigest()
    async with AsyncSessionLocal() as session:
        from app.models import Account
        res = await session.execute(select(Account).where(Account.account_id == account_id))
        acc = res.scalars().first()
        acc_uuid = acc.id
            
        token_entry = ExchangeToken(
            account_id=acc_uuid,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            is_initial_provisioning=False
        )
        session.add(token_entry)
        await session.commit()

    # 4. Exchange Token (second device GUID)
    device_2 = str(uuid.uuid4())
    print(f"\n--- Exchanging token for new device {device_2} ---")
    response = client.post("/api/auth/exchange", json={
        "exchange_token": exchange_token_str,
        "device_guid": device_2,
        "client_version": "1.0.0",
        "client_type": "desktop"
    })
    
    print(f"Exchange Status: {response.status_code}")
    print(f"Exchange Body: {response.json()}")
    
    if response.status_code == 200:
        access_token = response.json()["access_token"]
        
        print("\n--- Heartbeat for new device ---")
        response = client.get("/api/devices/status", headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Guid": device_2
        })
        print(f"Heartbeat Status: {response.status_code}")
        print(f"Heartbeat Body: {response.json()}")
