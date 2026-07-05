"""
test_billing_api.py — Integration Tests for Customer Billing REST API (Phase 2.7).

Verifies all authenticated billing endpoints, subscription state views, plan catalog listing,
payment history pagination, purchase initiation, auto-renew management, Anti-IDOR isolation (404 mapping),
and JWT security requirements.
"""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from app.database import get_db
from app.dependencies import get_razorpay_provider
from app.main import app
from app.models import PaymentStatus, SubscriptionLifecycleStatus
from app.models.payment import PaymentProviderType
from app.repositories import (
    AccountRepository,
    PaymentRepository,
    SubscriptionRepository,
)
from app.security import hash_master_token
from app.services.payment.provider import (
    PaymentOrderDTO,
    PaymentRefundDTO,
    PaymentVerificationDTO,
    PaymentWebhookDTO,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient configured with overridden database dependencies."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.create_order.return_value = PaymentOrderDTO(
        provider_order_id="order_test_123456",
        amount_minor_units=49900,
        currency="INR",
    )
    return provider


@pytest_asyncio.fixture(scope="function")
async def client_with_mock_provider(
    async_client: AsyncClient, mock_provider: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    """Yield AsyncClient with mocked RazorpayProvider dependency."""
    app.dependency_overrides[get_razorpay_provider] = lambda: mock_provider
    yield async_client
    if get_razorpay_provider in app.dependency_overrides:
        del app.dependency_overrides[get_razorpay_provider]


async def get_auth_headers(
    async_client: AsyncClient, account_factory, account_id: str = "RT-BILL-001"
) -> tuple[dict[str, str], any]:
    """Helper to create account, login, and return authorization header + account object."""
    master_token = secrets.token_hex(32)
    acc = await account_factory(
        account_id=account_id, master_token_hash=hash_master_token(master_token)
    )
    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": account_id,
            "master_token": master_token,
            "device_guid": f"dev-{account_id}",
        },
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, acc


# ── 1. Get Subscription Details ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_subscription_none(async_client: AsyncClient, account_factory):
    """GET /api/billing/subscription returns NONE status when no active subscription exists."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-SUB-NONE")
    resp = await async_client.get("/api/billing/subscription", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["lifecycle_status"] == "NONE"
    assert data["plan"] == "none"
    assert data["auto_renew"] is False


@pytest.mark.asyncio
async def test_get_subscription_active(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """GET /api/billing/subscription returns details when active subscription exists."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-SUB-ACT")

    sub_repo = SubscriptionRepository(db_session)
    now = datetime.now(timezone.utc)
    await sub_repo.create(
        account_id=acc.id,
        plan_id="pro",
        status=SubscriptionLifecycleStatus.ACTIVE,
        starts_at=now,
        expires_at=now + timedelta(days=30),
        auto_renew=True,
    )

    resp = await async_client.get("/api/billing/subscription", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["lifecycle_status"] == "ACTIVE"
    assert data["plan"] == "pro"
    assert data["auto_renew"] is True
    assert data["expires_at"] is not None


# ── 2. List Subscription Plans ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_plans(async_client: AsyncClient, account_factory):
    """GET /api/billing/plans returns list of available plans with pricing."""
    headers, _ = await get_auth_headers(async_client, account_factory, "RT-PLANS-1")
    resp = await async_client.get("/api/billing/plans", headers=headers)
    assert resp.status_code == 200, resp.text
    plans = resp.json()
    assert isinstance(plans, list)
    assert len(plans) >= 1

    plan_ids = {p["plan_id"] for p in plans}
    assert "pro" in plan_ids
    pro_plan = next(p for p in plans if p["plan_id"] == "pro")
    assert pro_plan["price"] > 0
    assert pro_plan["currency"] == "INR"


# ── 3. List Payments & Get Payment Detail ────────────────────────────────────
@pytest.mark.asyncio
async def test_list_payments_and_get_detail(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """GET /api/billing/payments returns paginated list and GET /api/billing/payment/{id} returns details."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-PAY-HIST")

    pay_repo = PaymentRepository(db_session)
    p1 = await pay_repo.create(
        account_id=acc.id,
        provider=PaymentProviderType.RAZORPAY,
        amount_minor_units=49900,
        currency="INR",
        status=PaymentStatus.CREATED,
        provider_order_id="order_test_100",
        idempotency_key="key_100",
    )
    p2 = await pay_repo.create(
        account_id=acc.id,
        provider=PaymentProviderType.RAZORPAY,
        amount_minor_units=49900,
        currency="INR",
        status=PaymentStatus.CREATED,
        provider_order_id="order_test_200",
        idempotency_key="key_200",
    )

    # List payments
    list_resp = await async_client.get(
        "/api/billing/payments?limit=10&offset=0", headers=headers
    )
    assert list_resp.status_code == 200, list_resp.text
    data = list_resp.json()
    assert data["total"] == 2
    assert len(data["payments"]) == 2
    order_ids = {p["payment_id"] for p in data["payments"]}
    assert order_ids == {"order_test_100", "order_test_200"}

    # Get single payment detail by provider order ID
    get_resp = await async_client.get(
        "/api/billing/payment/order_test_100", headers=headers
    )
    assert get_resp.status_code == 200, get_resp.text
    pay_data = get_resp.json()
    assert pay_data["payment_id"] == "order_test_100"
    assert pay_data["amount"] == 49900
    assert pay_data["status"] == "CREATED"


@pytest.mark.asyncio
async def test_get_payment_not_found(async_client: AsyncClient, account_factory):
    """GET /api/billing/payment/{id} returns 404 for nonexistent payment."""
    headers, _ = await get_auth_headers(async_client, account_factory, "RT-PAY-NF")
    resp = await async_client.get(
        "/api/billing/payment/order_nonexistent", headers=headers
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_payment_anti_idor(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """Anti-IDOR: Account B cannot read Account A's payment. Returns 404."""
    headers_a, acc_a = await get_auth_headers(
        async_client, account_factory, "RT-IDOR-A"
    )
    headers_b, acc_b = await get_auth_headers(
        async_client, account_factory, "RT-IDOR-B"
    )

    pay_repo = PaymentRepository(db_session)
    await pay_repo.create(
        account_id=acc_a.id,
        provider=PaymentProviderType.RAZORPAY,
        amount_minor_units=49900,
        currency="INR",
        status=PaymentStatus.CREATED,
        provider_order_id="order_secret_a",
        idempotency_key="key_secret_a",
    )

    # Account A can access
    resp_a = await async_client.get(
        "/api/billing/payment/order_secret_a", headers=headers_a
    )
    assert resp_a.status_code == 200, resp_a.text

    # Account B gets 404 Not Found (Anti-IDOR)
    resp_b = await async_client.get(
        "/api/billing/payment/order_secret_a", headers=headers_b
    )
    assert resp_b.status_code == 404, resp_b.text


# ── 4. Purchase Subscription Order ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_purchase_subscription_success(
    client_with_mock_provider: AsyncClient, account_factory, mock_provider: AsyncMock
):
    """POST /api/billing/purchase initiates order via payment gateway and returns order details."""
    headers, _ = await get_auth_headers(
        client_with_mock_provider, account_factory, "RT-PUR-1"
    )
    req_data = {
        "plan_id": "pro",
        "idempotency_key": "idem_purchase_001",
    }
    resp = await client_with_mock_provider.post(
        "/api/billing/purchase", json=req_data, headers=headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["payment_id"] == "order_test_123456"
    assert data["amount"] == 49900
    assert data["currency"] == "INR"
    assert data["status"] == "CREATED"
    assert mock_provider.create_order.call_count == 1


@pytest.mark.asyncio
async def test_purchase_subscription_ignores_client_supplied_amount(
    client_with_mock_provider: AsyncClient, account_factory, mock_provider: AsyncMock
):
    """
    Regression test for Finding C-1 (payment tampering).

    A malicious client attempts to purchase the 'pro' plan while smuggling a drastically
    reduced 'amount' field into the request payload. The server must never honor a
    client-supplied amount: PurchaseRequestDTO has no such field, so it is silently
    dropped by FastAPI/Pydantic request parsing, and the amount actually sent to the
    payment gateway must always equal the authoritative plan price (49900 for 'pro'),
    regardless of what the client attempted to smuggle in.
    """
    headers, _ = await get_auth_headers(
        client_with_mock_provider, account_factory, "RT-PUR-TAMPER"
    )
    tampered_req_data = {
        "plan_id": "pro",
        "idempotency_key": "idem_purchase_tamper_001",
        "amount": 100,  # Attacker attempts to pay 1 INR instead of the real 499 INR price.
    }
    resp = await client_with_mock_provider.post(
        "/api/billing/purchase", json=tampered_req_data, headers=headers
    )
    assert resp.status_code == 200, resp.text

    data = resp.json()
    # The response amount must reflect the real plan price, never the attacker-supplied value.
    assert data["amount"] == 49900

    # The amount actually requested from the payment gateway must be the plan price too.
    assert mock_provider.create_order.call_count == 1
    _, call_kwargs = mock_provider.create_order.call_args
    assert call_kwargs["amount_minor_units"] == 49900


@pytest.mark.asyncio
async def test_purchase_subscription_invalid_plan(
    client_with_mock_provider: AsyncClient, account_factory
):
    """POST /api/billing/purchase with invalid plan_id returns 400 Bad Request."""
    headers, _ = await get_auth_headers(
        client_with_mock_provider, account_factory, "RT-PUR-INV"
    )
    req_data = {
        "plan_id": "nonexistent_plan",
        "idempotency_key": "idem_purchase_inv",
    }
    resp = await client_with_mock_provider.post(
        "/api/billing/purchase", json=req_data, headers=headers
    )
    assert resp.status_code == 400, resp.text


# ── 5. Cancel & Reactivate Auto-Renew ────────────────────────────────────────
@pytest.mark.asyncio
async def test_cancel_and_reactivate_auto_renew(
    async_client: AsyncClient, account_factory, db_session: AsyncSession
):
    """POST /api/billing/cancel-auto-renew and /api/billing/reactivate update auto_renew flag."""
    headers, acc = await get_auth_headers(async_client, account_factory, "RT-RENEW-1")

    sub_repo = SubscriptionRepository(db_session)
    now = datetime.now(timezone.utc)
    await sub_repo.create(
        account_id=acc.id,
        plan_id="pro",
        status=SubscriptionLifecycleStatus.ACTIVE,
        starts_at=now,
        expires_at=now + timedelta(days=30),
        auto_renew=True,
    )

    # Cancel auto renew
    cancel_resp = await async_client.post(
        "/api/billing/cancel-auto-renew", headers=headers
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["auto_renew"] is False

    # Reactivate auto renew
    react_resp = await async_client.post("/api/billing/reactivate", headers=headers)
    assert react_resp.status_code == 200, react_resp.text
    assert react_resp.json()["auto_renew"] is True


# ── 6. Unauthenticated Access Protection ─────────────────────────────────────
@pytest.mark.asyncio
async def test_unauthenticated_access(async_client: AsyncClient):
    """All billing endpoints return 401 Unauthorized when Authorization header is missing."""
    endpoints = [
        ("GET", "/api/billing/subscription"),
        ("GET", "/api/billing/plans"),
        ("GET", "/api/billing/payments"),
        ("GET", "/api/billing/payment/order_123"),
        ("POST", "/api/billing/purchase", {"plan_id": "pro", "idempotency_key": "key"}),
        ("POST", "/api/billing/cancel-auto-renew"),
        ("POST", "/api/billing/reactivate"),
    ]
    for method, url, *payload in endpoints:
        if method == "GET":
            resp = await async_client.get(url)
        else:
            resp = await async_client.post(url, json=payload[0] if payload else None)
        assert resp.status_code == 401, (
            f"Expected 401 for {method} {url}, got {resp.status_code}: {resp.text}"
        )
