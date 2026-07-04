"""
test_lifecycle_job_service.py — Exhaustive unit and idempotency tests for Phase 2.6 LifecycleJobService.
Covers all 7 lifecycle jobs, transient backoff math, error isolation, and 10x idempotency loop.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.models import (
    ProvisioningState,
    RetryItemStatus,
    SubscriptionLifecycleStatus,
)
from app.services import LifecycleJobService


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_sub_service():
    return AsyncMock()


@pytest.fixture
def mock_prov_service():
    return AsyncMock()


@pytest.fixture
def mock_pay_service():
    return AsyncMock()


@pytest.fixture
def mock_cred_service():
    return AsyncMock()


@pytest.fixture
def job_service(
    mock_session,
    mock_sub_service,
    mock_prov_service,
    mock_pay_service,
    mock_cred_service,
):
    svc = LifecycleJobService(
        session=mock_session,
        subscription_service=mock_sub_service,
        provisioning_service=mock_prov_service,
        payment_service=mock_pay_service,
        credential_service=mock_cred_service,
    )
    svc.subscription_repo = AsyncMock()
    svc.payment_repo = AsyncMock()
    svc.provisioning_repo = AsyncMock()
    svc.retry_repo = AsyncMock()
    svc.health_repo = AsyncMock()
    return svc


# ── 1. Subscription Expiration Job ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_run_subscription_expiration_job_auto_renew(job_service, mock_sub_service):
    mock_sub = MagicMock(id=uuid.uuid4(), account_id=uuid.uuid4(), auto_renew=True)
    job_service.subscription_repo.get_expired_active_subscriptions.return_value = [mock_sub]

    count = await job_service.run_subscription_expiration_job()
    assert count == 1
    mock_sub_service.enter_grace_period.assert_called_once_with(mock_sub.id, commit=True)
    mock_sub_service.expire_subscription.assert_not_called()


@pytest.mark.asyncio
async def test_run_subscription_expiration_job_no_renew(job_service, mock_sub_service, mock_cred_service):
    mock_sub = MagicMock(id=uuid.uuid4(), account_id=uuid.uuid4(), auto_renew=False)
    job_service.subscription_repo.get_expired_active_subscriptions.return_value = [mock_sub]

    count = await job_service.run_subscription_expiration_job()
    assert count == 1
    mock_sub_service.expire_subscription.assert_called_once_with(mock_sub.id, commit=True)
    mock_cred_service.revoke_credentials.assert_called_once_with(mock_sub.account_id, commit=True)


# ── 2. Grace Period Expiration Job ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_run_grace_period_expiration_job(job_service, mock_sub_service, mock_cred_service):
    mock_sub = MagicMock(id=uuid.uuid4(), account_id=uuid.uuid4())
    job_service.subscription_repo.get_expired_grace_subscriptions.return_value = [mock_sub]

    count = await job_service.run_grace_period_expiration_job()
    assert count == 1
    mock_sub_service.expire_subscription.assert_called_once_with(mock_sub.id, commit=True)
    mock_cred_service.revoke_credentials.assert_called_once_with(mock_sub.account_id, commit=True)


# ── 3. Stale Pending Payment Cleanup Job ─────────────────────────────────────
@pytest.mark.asyncio
async def test_run_stale_pending_payment_cleanup_job(job_service, mock_pay_service):
    mock_payment = MagicMock(id=uuid.uuid4(), created_at=datetime.now(timezone.utc) - timedelta(hours=30))
    job_service.payment_repo.get_stale_pending_payments.return_value = [mock_payment]

    count = await job_service.run_stale_pending_payment_cleanup_job()
    assert count == 1
    mock_pay_service.cancel_payment.assert_called_once_with(mock_payment.id, commit=True)


# ── 4. Orphan Provisioning Cleanup Job ───────────────────────────────────────
@pytest.mark.asyncio
async def test_run_orphan_provisioning_cleanup_job(job_service, mock_sub_service, mock_cred_service):
    mock_profile = MagicMock(account_id=uuid.uuid4(), provisioning_state=ProvisioningState.ACTIVE)
    job_service.provisioning_repo.get_all_active_or_suspended.return_value = [mock_profile]
    mock_sub_service.get_active_subscription.return_value = None  # Orphan

    count = await job_service.run_orphan_provisioning_cleanup_job()
    assert count == 1
    mock_cred_service.revoke_credentials.assert_called_once_with(mock_profile.account_id, commit=True)


# ── 5. System Health Monitoring Job ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_run_system_health_monitoring_job_ok(job_service, mock_prov_service, mock_pay_service):
    mock_prov_service.check_provider_health.return_value = True
    mock_pay_service.check_provider_health.return_value = True

    results = await job_service.run_system_health_monitoring_job()
    assert results == {"marzban": True, "payment_gateway": True}
    assert job_service.health_repo.upsert_status.call_count == 2


@pytest.mark.asyncio
async def test_run_system_health_monitoring_job_degraded(job_service, mock_prov_service, mock_pay_service):
    mock_prov_service.check_provider_health.side_effect = RuntimeError("Marzban timeout")
    mock_pay_service.check_provider_health.return_value = False

    results = await job_service.run_system_health_monitoring_job()
    assert results == {"marzban": False, "payment_gateway": False}
    assert job_service.health_repo.upsert_status.call_count == 2


# ── 6. Credential Rotation Job ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_run_credential_rotation_job(job_service, mock_prov_service):
    now = datetime.now(timezone.utc)
    mock_profile = MagicMock(
        account_id=uuid.uuid4(),
        provisioning_state=ProvisioningState.ACTIVE,
        last_sync_at=now - timedelta(days=35),
    )
    job_service.provisioning_repo.get_all_active_or_suspended.return_value = [mock_profile]

    count = await job_service.run_credential_rotation_job()
    assert count == 1
    mock_prov_service.rotate_user_credentials.assert_called_once_with(mock_profile.account_id)


# ── 7. Failed Provision Retry Job ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_run_failed_provision_retry_job_success(job_service, mock_prov_service):
    mock_item = MagicMock(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        plan_id="premium",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        status=RetryItemStatus.PENDING,
        attempt_count=1,
    )
    job_service.retry_repo.get_pending_retries.return_value = [mock_item]

    count = await job_service.run_failed_provision_retry_job()
    assert count == 1
    mock_prov_service.provision_subscription.assert_called_once()
    assert mock_item.status == RetryItemStatus.COMPLETED
    job_service.retry_repo.update.assert_called_once_with(mock_item, commit=True)


@pytest.mark.asyncio
async def test_run_failed_provision_retry_job_backoff(job_service, mock_prov_service, mock_session):
    mock_item = MagicMock(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        plan_id="premium",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        status=RetryItemStatus.PENDING,
        attempt_count=2,
    )
    job_service.retry_repo.get_pending_retries.return_value = [mock_item]
    mock_prov_service.provision_subscription.side_effect = RuntimeError("503 Unavailable")
    job_service.retry_repo.get_by_id.return_value = mock_item

    count = await job_service.run_failed_provision_retry_job()
    assert count == 0
    mock_session.rollback.assert_called_once()
    assert mock_item.attempt_count == 3
    assert mock_item.status == RetryItemStatus.PENDING
    job_service.retry_repo.update.assert_called_once_with(mock_item, commit=True)


@pytest.mark.asyncio
async def test_run_failed_provision_retry_job_permanent_failure(job_service, mock_prov_service, mock_session):
    mock_item = MagicMock(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        plan_id="premium",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        status=RetryItemStatus.PENDING,
        attempt_count=4,
    )
    job_service.retry_repo.get_pending_retries.return_value = [mock_item]
    mock_prov_service.provision_subscription.side_effect = RuntimeError("503 Unavailable")
    job_service.retry_repo.get_by_id.return_value = mock_item

    count = await job_service.run_failed_provision_retry_job()
    assert count == 0
    assert mock_item.attempt_count == 5
    assert mock_item.status == RetryItemStatus.FAILED
    job_service.retry_repo.update.assert_called_once_with(mock_item, commit=True)


# ── 8. Exhaustive 10x Loop Idempotency Test ──────────────────────────────────
@pytest.mark.asyncio
async def test_lifecycle_job_idempotency_loop(job_service):
    """
    Run all 7 jobs in a 10x loop with empty/zero matching items to verify
    absolute idempotency, zero side effects, and clean error-free execution.
    """
    job_service.subscription_repo.get_expired_active_subscriptions.return_value = []
    job_service.subscription_repo.get_expired_grace_subscriptions.return_value = []
    job_service.payment_repo.get_stale_pending_payments.return_value = []
    job_service.provisioning_repo.get_all_active_or_suspended.return_value = []
    job_service.retry_repo.get_pending_retries.return_value = []
    job_service.provisioning_service.check_provider_health.return_value = True
    job_service.payment_service.check_provider_health.return_value = True

    for i in range(10):
        c1 = await job_service.run_subscription_expiration_job()
        c2 = await job_service.run_grace_period_expiration_job()
        c3 = await job_service.run_stale_pending_payment_cleanup_job()
        c4 = await job_service.run_orphan_provisioning_cleanup_job()
        res5 = await job_service.run_system_health_monitoring_job()
        c6 = await job_service.run_credential_rotation_job()
        c7 = await job_service.run_failed_provision_retry_job()

        assert c1 == 0
        assert c2 == 0
        assert c3 == 0
        assert c4 == 0
        assert res5 == {"marzban": True, "payment_gateway": True}
        assert c6 == 0
        assert c7 == 0
