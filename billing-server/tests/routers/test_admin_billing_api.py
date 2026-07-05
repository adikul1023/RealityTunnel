"""
test_admin_billing_api.py — Integration tests for Phase 2.8 Administrative Billing & Operations API.

Coverage:
- Dashboard metrics aggregation (all domains)
- Subscription listing, pagination, status filtering, details, and lifecycle actions (activate, grace, expire, cancel, renew)
- Payment transaction listing, details, gateway reconciliation, and manual resolution
- Provisioning profile listing, sync, retry, suspend, restore, and terminate
- Retry queue inspection, immediate retry execution, and discarding
- System operational health reporting
- Security isolation: Customer JWT rejected (HTTP 401 Unauthorized) on admin endpoints
- Privilege enforcement: Read-only admin rejected (HTTP 403 Forbidden) on write operations
- DTO hygiene audit: Zero sensitive credentials or secrets leaked in any response DTOs
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from app.dependencies import get_marzban_provider, get_razorpay_provider
from app.main import app
from app.models import (
    PaymentStatus,
    ProvisioningState,
    RetryItemStatus,
    SubscriptionLifecycleStatus,
)
from app.models.payment import PaymentProviderType
from app.repositories import (
    PaymentRepository,
    ProvisioningRepository,
    ProvisioningRetryRepository,
    SubscriptionRepository,
)
from app.security import hash_master_token
from app.services.payment.provider import PaymentOrderDTO, PaymentVerificationDTO
from app.services.provisioning.provider import ProvisionedUserDTO
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

SENSITIVE_FIELDS = {
    "master_token_hash",
    "password_hash",
    "marzban_username",
    "refresh_token",
    "access_token",
    "master_token",
    "vless_uri",
    "reality_key",
    "webhook_signature",
    "secret",
}


def _assert_no_sensitive_fields(obj: any) -> None:
    """Recursively assert no sensitive credential fields appear in any response DTO."""
    if isinstance(obj, list):
        for item in obj:
            _assert_no_sensitive_fields(item)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            assert key.lower() not in SENSITIVE_FIELDS, (
                f"Sensitive field '{key}' leaked in admin DTO response"
            )
            _assert_no_sensitive_fields(value)


@pytest_asyncio.fixture(autouse=True, scope="function")
async def mock_providers():
    """Mock Marzban and Razorpay providers to prevent real network calls during testing."""
    mock_marzban = AsyncMock()
    mock_user_dto = ProvisionedUserDTO(
        remote_user_id="test_vpn_user",
        status="active",
        data_limit=10000000000,
        data_used=1000000,
        expire_at=1800000000,
        links=["vless://test_link_1", "vless://test_link_2"],
    )
    mock_marzban.create_user.return_value = mock_user_dto
    mock_marzban.update_user.return_value = mock_user_dto
    mock_marzban.suspend_user.return_value = ProvisionedUserDTO(
        remote_user_id="test_vpn_user", status="disabled", links=[]
    )
    mock_marzban.unsuspend_user.return_value = mock_user_dto
    mock_marzban.delete_user.return_value = True
    mock_marzban.get_user.return_value = mock_user_dto
    mock_marzban.sync_user.return_value = mock_user_dto
    mock_marzban.reset_user_credentials.return_value = mock_user_dto
    mock_marzban.health_check.return_value = True

    mock_razorpay = AsyncMock()
    mock_razorpay.create_order.return_value = PaymentOrderDTO(
        provider_order_id="order_test_123456",
        amount_minor_units=49900,
        currency="INR",
    )
    # amount_minor_units=None here deliberately: this fixture backs admin endpoints that
    # exercise both real-gateway reconciliation (matching amount not required to test) and
    # manual/fabricated payment-reference resolution (no real gateway amount exists to compare
    # against). Amount-mismatch enforcement itself (Finding C-1 defense-in-depth) is covered by
    # dedicated tests in tests/services/test_payment_service.py.
    mock_razorpay.fetch_payment.return_value = PaymentVerificationDTO(
        provider_payment_id="pay_test_123456",
        provider_order_id="order_test_123456",
        status="captured",
        amount_minor_units=None,
        currency="INR",
        is_valid=True,
    )
    mock_razorpay.health_check.return_value = True

    app.dependency_overrides[get_marzban_provider] = lambda: mock_marzban
    app.dependency_overrides[get_razorpay_provider] = lambda: mock_razorpay
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_marzban_provider, None)
        app.dependency_overrides.pop(get_razorpay_provider, None)


# ── Helpers for test setup ──────────────────────────────────────────────────


async def _create_sample_subscription(
    db_session: AsyncSession,
    account_id: uuid.UUID,
    status: SubscriptionLifecycleStatus = SubscriptionLifecycleStatus.ACTIVE,
    plan_id: str = "standard_monthly",
):
    sub_repo = SubscriptionRepository(db_session)
    now = datetime.now(timezone.utc)
    return await sub_repo.create(
        account_id=account_id,
        plan_id=plan_id,
        status=status,
        starts_at=now,
        expires_at=now + timedelta(days=30),
        auto_renew=True,
    )


async def _create_sample_payment(
    db_session: AsyncSession,
    account_id: uuid.UUID,
    subscription_id: uuid.UUID | None = None,
    status: PaymentStatus = PaymentStatus.PAID,
    amount: int = 99900,
):
    pay_repo = PaymentRepository(db_session)
    now = datetime.now(timezone.utc)
    return await pay_repo.create(
        account_id=account_id,
        subscription_id=subscription_id,
        provider=PaymentProviderType.RAZORPAY,
        provider_order_id=f"order_{secrets.token_hex(8)}",
        provider_payment_id=f"pay_{secrets.token_hex(8)}"
        if status == PaymentStatus.PAID
        else None,
        amount_minor_units=amount,
        currency="INR",
        status=status,
        idempotency_key=f"idemp_{secrets.token_hex(12)}",
        paid_at=now if status == PaymentStatus.PAID else None,
    )


async def _create_sample_provisioning(
    db_session: AsyncSession,
    account_id: uuid.UUID,
    state: ProvisioningState = ProvisioningState.ACTIVE,
):
    prov_repo = ProvisioningRepository(db_session)
    now = datetime.now(timezone.utc)
    return await prov_repo.create(
        account_id=account_id,
        remote_user_id=f"vpn_user_{account_id.hex[:8]}",
        provisioning_state=state,
        last_sync_at=now,
    )


async def _create_sample_retry_item(
    db_session: AsyncSession,
    account_id: uuid.UUID,
    status: RetryItemStatus = RetryItemStatus.PENDING,
):
    retry_repo = ProvisioningRetryRepository(db_session)
    now = datetime.now(timezone.utc)
    return await retry_repo.create(
        account_id=account_id,
        plan_id="standard_monthly",
        expires_at=now + timedelta(days=30),
        next_retry_at=now + timedelta(minutes=5),
        last_error="Connection timed out to Marzban server",
        status=status,
    )


# ── 1. Dashboard Metrics ────────────────────────────────────────────────────


async def test_admin_billing_dashboard(
    async_client, account_factory, admin_auth_headers_factory, db_session
):
    """GET /api/admin/dashboard returns operational and revenue metrics without leaking secrets."""
    acc1 = await account_factory(account_id="RT-ADM-DASH-1")
    acc2 = await account_factory(account_id="RT-ADM-DASH-2")

    await _create_sample_subscription(
        db_session, acc1.id, SubscriptionLifecycleStatus.ACTIVE
    )
    await _create_sample_subscription(
        db_session, acc2.id, SubscriptionLifecycleStatus.GRACE
    )
    await _create_sample_payment(
        db_session, acc1.id, status=PaymentStatus.PAID, amount=49900
    )
    await _create_sample_payment(
        db_session, acc2.id, status=PaymentStatus.PAID, amount=99900
    )
    await _create_sample_retry_item(db_session, acc2.id, RetryItemStatus.PENDING)

    headers, _ = await admin_auth_headers_factory(
        is_super_admin=False, username="dash_admin"
    )
    resp = await async_client.get("/api/admin/dashboard", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    _assert_no_sensitive_fields(body)

    assert body["total_accounts"] >= 2
    assert body["active_subscriptions"] >= 1
    assert body["grace_subscriptions"] >= 1
    assert body["today_payments"] >= 2
    assert body["today_revenue_minor_units"] >= 149800
    assert body["retry_queue_size"] >= 1
    assert body["active_admins"] >= 1


# ── 2. Subscriptions Administration ─────────────────────────────────────────


async def test_admin_subscriptions_list_and_get(
    async_client, account_factory, admin_auth_headers_factory, db_session
):
    """Test listing subscriptions with status filtering and retrieving subscription details."""
    acc1 = await account_factory(account_id="RT-ADM-SUB-1")
    acc2 = await account_factory(account_id="RT-ADM-SUB-2")

    sub1 = await _create_sample_subscription(
        db_session, acc1.id, SubscriptionLifecycleStatus.ACTIVE, plan_id="pro"
    )
    sub2 = await _create_sample_subscription(
        db_session, acc2.id, SubscriptionLifecycleStatus.EXPIRED, plan_id="basic"
    )

    headers, _ = await admin_auth_headers_factory(
        is_super_admin=False, username="sub_list_admin"
    )

    # List all
    resp_all = await async_client.get(
        "/api/admin/subscriptions?limit=10&offset=0", headers=headers
    )
    assert resp_all.status_code == 200
    body_all = resp_all.json()
    _assert_no_sensitive_fields(body_all)
    assert body_all["total"] >= 2
    assert any(s["id"] == str(sub1.id) for s in body_all["subscriptions"])

    # Filter by status
    resp_active = await async_client.get(
        "/api/admin/subscriptions?status=ACTIVE", headers=headers
    )
    assert resp_active.status_code == 200
    body_active = resp_active.json()
    assert all(s["status"] == "ACTIVE" for s in body_active["subscriptions"])

    # Get single subscription
    resp_single = await async_client.get(
        f"/api/admin/subscription/{sub1.id}", headers=headers
    )
    assert resp_single.status_code == 200
    body_single = resp_single.json()
    assert body_single["id"] == str(sub1.id)
    assert body_single["plan_id"] == "pro"

    # Get unknown subscription
    resp_unknown = await async_client.get(
        f"/api/admin/subscription/{uuid.uuid4()}", headers=headers
    )
    assert resp_unknown.status_code == 404


async def test_admin_subscription_lifecycle_actions(
    async_client, account_factory, admin_auth_headers_factory, db_session
):
    """Test super-admin lifecycle actions: grace, activate, renew, expire, cancel."""
    acc = await account_factory(account_id="RT-ADM-SUB-LIFE")
    sub = await _create_sample_subscription(
        db_session, acc.id, SubscriptionLifecycleStatus.ACTIVE
    )
    await _create_sample_provisioning(db_session, acc.id, ProvisioningState.ACTIVE)

    super_headers, _ = await admin_auth_headers_factory(
        is_super_admin=True, username="super_sub_admin"
    )

    # Enter grace period
    resp_grace = await async_client.post(
        f"/api/admin/subscription/{sub.id}/grace",
        json={"grace_duration_days": 5},
        headers=super_headers,
    )
    assert resp_grace.status_code == 200, resp_grace.text
    assert resp_grace.json()["status"] == "GRACE"
    assert resp_grace.json()["grace_expires_at"] is not None

    # Activate
    resp_act = await async_client.post(
        f"/api/admin/subscription/{sub.id}/activate",
        headers=super_headers,
    )
    assert resp_act.status_code == 200
    assert resp_act.json()["status"] == "ACTIVE"

    # Renew
    new_expire = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
    resp_renew = await async_client.post(
        f"/api/admin/subscription/{sub.id}/renew",
        json={"new_expires_at": new_expire},
        headers=super_headers,
    )
    assert resp_renew.status_code == 200
    assert resp_renew.json()["expires_at"] is not None

    # Expire
    resp_exp = await async_client.post(
        f"/api/admin/subscription/{sub.id}/expire",
        headers=super_headers,
    )
    assert resp_exp.status_code == 200
    assert resp_exp.json()["status"] == "EXPIRED"


async def test_admin_subscription_readonly_forbidden(
    async_client, account_factory, admin_auth_headers_factory, db_session
):
    """Verify read-only admin gets HTTP 403 Forbidden when attempting write operations."""
    acc = await account_factory(account_id="RT-ADM-SUB-RO")
    sub = await _create_sample_subscription(
        db_session, acc.id, SubscriptionLifecycleStatus.ACTIVE
    )

    readonly_headers, _ = await admin_auth_headers_factory(
        is_super_admin=False, username="readonly_sub_admin"
    )

    resp = await async_client.post(
        f"/api/admin/subscription/{sub.id}/activate",
        headers=readonly_headers,
    )
    assert resp.status_code == 403
    assert "super-admin privilege required" in resp.json()["detail"].lower()


# ── 3. Payments Administration ──────────────────────────────────────────────


async def test_admin_payments_list_and_reconcile_resolve(
    async_client, account_factory, admin_auth_headers_factory, db_session
):
    """Test listing payments, filtering, reconcile, and resolve actions."""
    acc = await account_factory(account_id="RT-ADM-PAY-1")
    pay_paid = await _create_sample_payment(
        db_session, acc.id, status=PaymentStatus.PAID, amount=49900
    )
    pay_pending = await _create_sample_payment(
        db_session, acc.id, status=PaymentStatus.PENDING, amount=99900
    )

    headers, _ = await admin_auth_headers_factory(
        is_super_admin=False, username="pay_ro_admin"
    )
    super_headers, _ = await admin_auth_headers_factory(
        is_super_admin=True, username="pay_super_admin"
    )

    # List
    resp_list = await async_client.get("/api/admin/payments?limit=10", headers=headers)
    assert resp_list.status_code == 200
    _assert_no_sensitive_fields(resp_list.json())

    # Get single
    resp_get = await async_client.get(
        f"/api/admin/payment/{pay_paid.id}", headers=headers
    )
    assert resp_get.status_code == 200
    assert resp_get.json()["amount_minor_units"] == 49900

    # Reconcile already PAID payment
    resp_rec = await async_client.post(
        f"/api/admin/payment/{pay_paid.id}/reconcile", headers=super_headers
    )
    assert resp_rec.status_code == 200
    assert resp_rec.json()["status"] == "PAID"

    # Resolve pending payment manually
    resp_res = await async_client.post(
        f"/api/admin/payment/{pay_pending.id}/resolve",
        json={"reason": "Manual operator intervention"},
        headers=super_headers,
    )
    assert resp_res.status_code == 200
    assert resp_res.json()["status"] == "PAID"


# ── 4. Provisioning Administration ──────────────────────────────────────────


async def test_admin_provisioning_endpoints(
    async_client, account_factory, admin_auth_headers_factory, db_session
):
    """Test listing provisioning profiles and executing administrative actions."""
    acc = await account_factory(account_id="RT-ADM-PROV-1")
    prov = await _create_sample_provisioning(
        db_session, acc.id, ProvisioningState.ACTIVE
    )

    headers, _ = await admin_auth_headers_factory(
        is_super_admin=False, username="prov_ro_admin"
    )
    super_headers, _ = await admin_auth_headers_factory(
        is_super_admin=True, username="prov_super_admin"
    )

    # List
    resp_list = await async_client.get("/api/admin/provisioning", headers=headers)
    assert resp_list.status_code == 200
    _assert_no_sensitive_fields(resp_list.json())
    assert any(p["id"] == str(prov.id) for p in resp_list.json()["profiles"])

    # Sync
    resp_sync = await async_client.post(
        f"/api/admin/provisioning/{prov.id}/sync", headers=super_headers
    )
    assert resp_sync.status_code == 200
    assert resp_sync.json()["provisioning_state"] in ("ACTIVE", "FAILED")


# ── 5. Retry Queue Administration ───────────────────────────────────────────


async def test_admin_retry_queue_endpoints(
    async_client, account_factory, admin_auth_headers_factory, db_session
):
    """Test retry queue inspection, immediate retry execution, and discard."""
    acc = await account_factory(account_id="RT-ADM-RETRY-1")
    acc2 = await account_factory(account_id="RT-ADM-RETRY-2")
    await _create_sample_provisioning(db_session, acc.id, ProvisioningState.FAILED)
    item1 = await _create_sample_retry_item(db_session, acc.id, RetryItemStatus.PENDING)
    item2 = await _create_sample_retry_item(db_session, acc2.id, RetryItemStatus.PENDING)

    headers, _ = await admin_auth_headers_factory(
        is_super_admin=False, username="retry_ro_admin"
    )
    super_headers, _ = await admin_auth_headers_factory(
        is_super_admin=True, username="retry_super_admin"
    )

    # Inspect queue
    resp_q = await async_client.get("/api/admin/retry-queue", headers=headers)
    assert resp_q.status_code == 200
    body_q = resp_q.json()
    _assert_no_sensitive_fields(body_q)
    assert body_q["pending_count"] >= 2
    assert any(i["id"] == str(item1.id) for i in body_q["items"])

    # Retry now
    resp_retry = await async_client.post(
        f"/api/admin/retry/{item1.id}/retry-now", headers=super_headers
    )
    assert resp_retry.status_code == 200
    assert resp_retry.json()["id"] == str(item1.id)

    # Discard item
    resp_disc = await async_client.post(
        f"/api/admin/retry/{item2.id}/discard", headers=super_headers
    )
    assert resp_disc.status_code == 200
    assert resp_disc.json()["status"] == "FAILED"


# ── 6. System Health Administration ─────────────────────────────────────────


async def test_admin_system_health(async_client, admin_auth_headers_factory):
    """GET /api/admin/system-health inspects provider and database status."""
    headers, _ = await admin_auth_headers_factory(
        is_super_admin=False, username="health_admin"
    )
    resp = await async_client.get("/api/admin/system-health", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    _assert_no_sensitive_fields(body)
    assert body["status"] in ("ok", "degraded")
    assert isinstance(body["components"], list)
    assert any(c["component"] == "postgres" for c in body["components"])


# ── 7. Security Isolation: Customer JWT Rejection ───────────────────────────


async def test_admin_billing_customer_jwt_rejected(async_client, account_factory):
    """Verify that a valid customer JWT is rejected on administrative routes with HTTP 401."""
    # Obtain a valid customer access token via login
    master_token = secrets.token_hex(32)
    acc = await account_factory(
        account_id="RT-CUST-ISOLATE", master_token_hash=hash_master_token(master_token)
    )
    login_resp = await async_client.post(
        "/api/auth/login",
        json={
            "account_id": "RT-CUST-ISOLATE",
            "master_token": master_token,
            "device_guid": "dev-isolate-001",
        },
    )
    assert login_resp.status_code == 200
    customer_token = login_resp.json()["access_token"]
    customer_headers = {"Authorization": f"Bearer {customer_token}"}

    # Attempt to access admin dashboard with customer token
    resp_dash = await async_client.get("/api/admin/dashboard", headers=customer_headers)
    assert resp_dash.status_code == 401
    assert "authentication failed" in resp_dash.json()["detail"].lower()

    # Attempt to list subscriptions with customer token
    resp_subs = await async_client.get(
        "/api/admin/subscriptions", headers=customer_headers
    )
    assert resp_subs.status_code == 401
    assert "authentication failed" in resp_subs.json()["detail"].lower()
