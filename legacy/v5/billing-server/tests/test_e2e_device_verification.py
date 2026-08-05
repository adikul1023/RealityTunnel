import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.account import Account
from app.models.device import Device
import secrets
from app.security.crypto import hash_master_token

@pytest.mark.asyncio
async def test_verify_client_type_device_creation(async_client, db_session: AsyncSession, account_factory):
    account_id = "RT-WEB-TEST-2"
    master_token = secrets.token_hex(32)
    master_token_hash = hash_master_token(master_token)
    
    # 1. Setup mock account in DB
    acc = await account_factory(account_id=account_id, master_token_hash=master_token_hash, plan_id="standard")
    
    # Verify no devices initially
    res = await db_session.execute(select(Device).where(Device.account_id == acc.id))
    devices = res.scalars().all()
    assert len(devices) == 0

    # 2. Simulate DESKTOP login
    desktop_resp = await async_client.post("/api/auth/login", json={
        "account_id": account_id,
        "master_token": master_token,
        "device_guid": "desktop-guid-1",
        "client_type": "desktop"
    })
    assert desktop_resp.status_code == 200, desktop_resp.text
    
    res = await db_session.execute(select(Device).where(Device.account_id == acc.id))
    devices = res.scalars().all()
    assert len(devices) == 1, "Desktop login should create exactly 1 device record"
    assert devices[0].device_guid == "desktop-guid-1"
    
    # 3. Simulate WEB login
    web_resp = await async_client.post("/api/auth/login", json={
        "account_id": account_id,
        "master_token": master_token,
        "device_guid": "web-guid-1",
        "client_type": "web"
    })
    assert web_resp.status_code == 200, web_resp.text
    
    res = await db_session.execute(select(Device).where(Device.account_id == acc.id))
    devices = res.scalars().all()
    # Still 1 device (the desktop one). Web login should not create a device.
    assert len(devices) == 1, "Web login should NOT create a device record"
    assert "web-guid-1" not in [d.device_guid for d in devices]
