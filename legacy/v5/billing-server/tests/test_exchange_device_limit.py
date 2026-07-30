"""
test_exchange_device_limit.py

Regression test for the exchange endpoint device-limit enforcement bug.

PREVIOUSLY BROKEN:
  POST /api/auth/exchange silently swallowed DeviceLimitExceededError and issued
  tokens for a device that was never registered in the DB. The device then failed
  every heartbeat with DEVICE_REMOVED. This was the root cause of the 15-minute
  connection drop for Basic/Quarterly subscribers using the SSO/exchange flow.

EXPECTED BEHAVIOUR AFTER FIX:
  POST /api/auth/exchange must return 403 DEVICE_LIMIT_EXCEEDED when the plan's
  device limit has already been reached — identical to POST /api/auth/login.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.main import app
from app.models import Account, ExchangeToken


@pytest.mark.asyncio
async def test_exchange_respects_device_limit():
    """
    Given:  An account on the 'quarterly' plan (1 device max) that already has
            one registered device (via normal login).
    When:   A second device attempts to authenticate via the exchange flow.
    Then:   POST /api/auth/exchange returns HTTP 403 with code DEVICE_LIMIT_EXCEEDED.
            No access token or refresh token is issued.
    """
    client = TestClient(app)

    # 1. Register a fresh account
    response = client.post("/api/auth/register", json={"plan_id": "quarterly", "device_type": "windows"})
    assert response.status_code == 201, f"Register failed: {response.json()}"
    account_data = response.json()
    account_id_str = account_data["account_id"]
    master_token = account_data["master_token"]

    # 2. First device logs in — consumes the single allowed device slot
    device_1 = str(uuid.uuid4())
    login_resp = client.post("/api/auth/login", json={
        "account_id": account_id_str,
        "master_token": master_token,
        "device_guid": device_1,
        "device_name": "First Device",
        "client_version": "1.0.0",
        "client_type": "desktop",
    })
    assert login_resp.status_code == 200, f"First login failed: {login_resp.json()}"

    # 3. Mint an exchange token for a NEW (second) device
    exchange_token_str = f"test-exchange-{uuid.uuid4()}"
    token_hash = hashlib.sha256(exchange_token_str.encode()).hexdigest()
    device_2 = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        acc = (await session.execute(
            select(Account).where(Account.account_id == account_id_str)
        )).scalars().first()
        assert acc is not None, "Account not found in DB"

        token_entry = ExchangeToken(
            account_id=acc.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            is_initial_provisioning=False,
        )
        session.add(token_entry)
        await session.commit()

    # 4. Attempt to redeem the exchange token for the second device
    exchange_resp = client.post("/api/auth/exchange", json={
        "exchange_token": exchange_token_str,
        "device_guid": device_2,
        "client_version": "1.0.0",
        "client_type": "desktop",
    })

    print(f"\nExchange Status: {exchange_resp.status_code}")
    print(f"Exchange Body:   {exchange_resp.json()}")

    # CORE ASSERTION: must be 403, not 200
    assert exchange_resp.status_code == 403, (
        f"Expected 403 DEVICE_LIMIT_EXCEEDED but got {exchange_resp.status_code}: "
        f"{exchange_resp.json()}"
    )

    body = exchange_resp.json()
    assert body.get("code") == "DEVICE_LIMIT_EXCEEDED", (
        f"Expected code=DEVICE_LIMIT_EXCEEDED, got: {body}"
    )

    # Confirm no tokens were leaked in the response
    assert "access_token" not in body, "No access_token should be present in a 403 response"
    assert "refresh_token" not in body, "No refresh_token should be present in a 403 response"
