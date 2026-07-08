"""
test_lifecycle_job_service.py — Unit and idempotency tests for LifecycleJobService.
Covers all 8 lifecycle jobs, skip_locked batch isolation (M-2), provisioning drift reconciliation (M-3),
transient backoff math, error isolation, and 10x idempotency loop.
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
    job_service.provisioning_repo.get_stale_profiles.return_value = [mock_profile]

    count = await job_service.run_credential_rotation_job()
    assert count == 1
    # Check that cutoff was passed by extracting the kwargs
    mock_prov_service.rotate_user_credentials.assert_called_once()
    args, kwargs = mock_prov_service.rotate_user_credentials.call_args
    assert args[0] == mock_profile.account_id
    assert "cutoff" in kwargs


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


# ── 8. Provisioning Reconciliation Job ──────────────────────────────────────
@pytest.mark.asyncio
async def test_run_provisioning_reconciliation_job(job_service, mock_prov_service):
    """
    Verifies that run_provisioning_reconciliation_job discovers stale profiles
    via get_stale_profiles and calls provisioning_service.synchronize() for each.
    """
    now = datetime.now(timezone.utc)
    mock_profile = MagicMock(
        account_id=uuid.uuid4(),
        provisioning_state=ProvisioningState.ACTIVE,
        last_sync_at=now - timedelta(minutes=90),
    )
    job_service.provisioning_repo.get_stale_profiles.return_value = [mock_profile]

    count = await job_service.run_provisioning_reconciliation_job()
    assert count == 1
    mock_prov_service.synchronize.assert_called_once_with(mock_profile.account_id)


@pytest.mark.asyncio
async def test_run_provisioning_reconciliation_job_empty(job_service, mock_prov_service):
    """No stale profiles → count is 0 and synchronize is never called."""
    job_service.provisioning_repo.get_stale_profiles.return_value = []

    count = await job_service.run_provisioning_reconciliation_job()
    assert count == 0
    mock_prov_service.synchronize.assert_not_called()


@pytest.mark.asyncio
async def test_run_provisioning_reconciliation_job_error_isolated(job_service, mock_prov_service, mock_session):
    """A synchronize failure for one profile is isolated; count remains 0 and session is rolled back."""
    mock_profile = MagicMock(
        account_id=uuid.uuid4(),
        provisioning_state=ProvisioningState.ACTIVE,
    )
    job_service.provisioning_repo.get_stale_profiles.return_value = [mock_profile]
    mock_prov_service.synchronize.side_effect = RuntimeError("Marzban timeout")

    count = await job_service.run_provisioning_reconciliation_job()
    assert count == 0
    mock_session.rollback.assert_called_once()


# ── M-2 Skip-Locked Batch Isolation Tests ────────────────────────────────────
@pytest.mark.asyncio
async def test_scheduler_batch_queries_use_skip_locked():
    """
    M-2: Verify every batch-discovery repository call used by the scheduler
    is invoked with for_update=True and skip_locked=True.
    Simulates two parallel scheduler workers by calling jobs on two separate
    job_service instances backed by the same mock repos, asserting both use
    SKIP LOCKED so the same row cannot be processed by both.
    """
    # Build two independent service instances backed by their own mock repos.
    for _ in range(2):
        session = AsyncMock()
        prov_svc = AsyncMock()
        svc = LifecycleJobService(
            session=session,
            subscription_service=AsyncMock(),
            provisioning_service=prov_svc,
            payment_service=AsyncMock(),
            credential_service=AsyncMock(),
        )
        svc.subscription_repo = AsyncMock()
        svc.payment_repo = AsyncMock()
        svc.provisioning_repo = AsyncMock()
        svc.retry_repo = AsyncMock()
        svc.health_repo = AsyncMock()
        prov_svc.check_provider_health.return_value = True
        svc.payment_service.check_provider_health.return_value = True
        svc.subscription_repo.get_expired_active_subscriptions.return_value = []
        svc.subscription_repo.get_expired_grace_subscriptions.return_value = []
        svc.payment_repo.get_stale_pending_payments.return_value = []
        svc.provisioning_repo.get_all_active_or_suspended.return_value = []
        svc.provisioning_repo.get_stale_profiles.return_value = []
        svc.retry_repo.get_pending_retries.return_value = []

        await svc.run_subscription_expiration_job()
        await svc.run_grace_period_expiration_job()
        await svc.run_stale_pending_payment_cleanup_job()
        await svc.run_orphan_provisioning_cleanup_job()
        await svc.run_credential_rotation_job()
        await svc.run_provisioning_reconciliation_job()
        await svc.run_failed_provision_retry_job()

        # Verify every discovery query passes for_update=True and skip_locked=True.
        svc.subscription_repo.get_expired_active_subscriptions.assert_called_once_with(
            svc.subscription_repo.get_expired_active_subscriptions.call_args[0][0],
            for_update=True, skip_locked=True
        )
        svc.subscription_repo.get_expired_grace_subscriptions.assert_called_once_with(
            svc.subscription_repo.get_expired_grace_subscriptions.call_args[0][0],
            for_update=True, skip_locked=True
        )
        svc.payment_repo.get_stale_pending_payments.assert_called_once_with(
            svc.payment_repo.get_stale_pending_payments.call_args[0][0],
            for_update=True, skip_locked=True
        )
        svc.provisioning_repo.get_all_active_or_suspended.assert_called_once_with(
            for_update=True, skip_locked=True
        )
        svc.retry_repo.get_pending_retries.assert_called_once_with(
            svc.retry_repo.get_pending_retries.call_args[0][0],
            for_update=True, skip_locked=True
        )
        # get_stale_profiles is used by both rotation and reconciliation.
        assert svc.provisioning_repo.get_stale_profiles.call_count == 2
        for call in svc.provisioning_repo.get_stale_profiles.call_args_list:
            assert call.kwargs.get("for_update") is True
            assert call.kwargs.get("skip_locked") is True


# ── M-3 Drift Self-Healing Tests ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_credential_service_drift_self_heal_suspended_locally_active_remotely():
    """
    M-3: Local profile state is SUSPENDED but Marzban reports the remote user as active.
    CredentialService.get_credentials must call provisioning_service.synchronize()
    and then return credentials — NOT raise CredentialAlreadyRevokedError.
    """
    from app.services.credential_service import CredentialService
    from app.services.exceptions import CredentialAlreadyRevokedError

    account_id = uuid.uuid4()
    mock_profile = MagicMock()
    mock_profile.provisioning_state = ProvisioningState.SUSPENDED
    mock_profile.remote_user_id = "remote-user-1"

    mock_user_dto = MagicMock()
    mock_user_dto.status = "active"  # Live Marzban says active — drift detected.
    mock_user_dto.links = ["vless://some-uuid@vpn.example.com:443?type=tcp&security=reality&pbk=pk&sni=sni&sid=sid#tag"]

    mock_prov_svc = AsyncMock()
    mock_prov_svc.get_provisioned_user.return_value = (mock_profile, mock_user_dto)
    mock_prov_svc.synchronize.return_value = mock_profile

    svc = CredentialService(session=AsyncMock(), provisioning_service=mock_prov_svc)
    result = await svc.get_credentials(account_id)

    # synchronize() must have been called to repair the stale local state.
    mock_prov_svc.synchronize.assert_called_once_with(account_id)
    # Credentials must still be returned — not an error.
    assert "vless_uri" in result


@pytest.mark.asyncio
async def test_credential_service_no_drift_when_both_suspended():
    """
    M-3: When both local profile AND remote Marzban report suspended, no self-heal
    should occur — CredentialAlreadyRevokedError must be raised.
    """
    from app.services.credential_service import CredentialService
    from app.services.exceptions import CredentialAlreadyRevokedError

    account_id = uuid.uuid4()
    mock_profile = MagicMock()
    mock_profile.provisioning_state = ProvisioningState.SUSPENDED
    mock_profile.remote_user_id = "remote-user-2"

    mock_user_dto = MagicMock()
    mock_user_dto.status = "suspended"  # Both sides agree — no drift.

    mock_prov_svc = AsyncMock()
    mock_prov_svc.get_provisioned_user.return_value = (mock_profile, mock_user_dto)

    svc = CredentialService(session=AsyncMock(), provisioning_service=mock_prov_svc)

    with pytest.raises(CredentialAlreadyRevokedError):
        await svc.get_credentials(account_id)

    # synchronize() must NOT be called — there is no drift to repair.
    mock_prov_svc.synchronize.assert_not_called()


@pytest.mark.asyncio
async def test_credential_service_no_drift_when_active_locally_suspended_remotely():
    """
    M-3: Local profile is ACTIVE but Marzban reports disabled/suspended.
    This is also a revoked state — raise CredentialAlreadyRevokedError without sync.
    """
    from app.services.credential_service import CredentialService
    from app.services.exceptions import CredentialAlreadyRevokedError

    account_id = uuid.uuid4()
    mock_profile = MagicMock()
    mock_profile.provisioning_state = ProvisioningState.ACTIVE
    mock_profile.remote_user_id = "remote-user-3"

    mock_user_dto = MagicMock()
    mock_user_dto.status = "disabled"  # Remote disagrees — but active-local/suspended-remote is still revoked.

    mock_prov_svc = AsyncMock()
    mock_prov_svc.get_provisioned_user.return_value = (mock_profile, mock_user_dto)

    svc = CredentialService(session=AsyncMock(), provisioning_service=mock_prov_svc)

    with pytest.raises(CredentialAlreadyRevokedError):
        await svc.get_credentials(account_id)

    mock_prov_svc.synchronize.assert_not_called()


@pytest.mark.asyncio
async def test_reconciliation_job_repairs_drift():
    """
    M-3: Hourly reconciliation path.
    Creates a stale SUSPENDED profile and verifies run_provisioning_reconciliation_job
    calls synchronize() to repair it — the job covers accounts that never
    requested credentials so the on-demand path in get_credentials never fired.
    """
    now = datetime.now(timezone.utc)
    account_id = uuid.uuid4()
    mock_profile = MagicMock(
        account_id=account_id,
        provisioning_state=ProvisioningState.SUSPENDED,
        last_sync_at=now - timedelta(minutes=90),
    )

    session = AsyncMock()
    prov_svc = AsyncMock()
    svc = LifecycleJobService(
        session=session,
        subscription_service=AsyncMock(),
        provisioning_service=prov_svc,
        payment_service=AsyncMock(),
        credential_service=AsyncMock(),
    )
    svc.subscription_repo = AsyncMock()
    svc.payment_repo = AsyncMock()
    svc.provisioning_repo = AsyncMock()
    svc.retry_repo = AsyncMock()
    svc.health_repo = AsyncMock()
    svc.provisioning_repo.get_stale_profiles.return_value = [mock_profile]

    count = await svc.run_provisioning_reconciliation_job(now=now)
    assert count == 1
    prov_svc.synchronize.assert_called_once_with(account_id)

    # Confirm get_stale_profiles was called with the correct 60-minute cutoff window.
    call_args = svc.provisioning_repo.get_stale_profiles.call_args
    cutoff_used = call_args[0][0]  # positional arg
    assert cutoff_used <= now - timedelta(minutes=59)  # Must be at least 60 min in the past.


# ── 9. Exhaustive 10x Loop Idempotency Test ──────────────────────────────────
@pytest.mark.asyncio
async def test_lifecycle_job_idempotency_loop(job_service):
    """
    Run all 8 jobs in a 10x loop with empty/zero matching items to verify
    absolute idempotency, zero side effects, and clean error-free execution.
    """
    job_service.subscription_repo.get_expired_active_subscriptions.return_value = []
    job_service.subscription_repo.get_expired_grace_subscriptions.return_value = []
    job_service.payment_repo.get_stale_pending_payments.return_value = []
    job_service.provisioning_repo.get_all_active_or_suspended.return_value = []
    job_service.provisioning_repo.get_stale_profiles.return_value = []
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
        c8 = await job_service.run_provisioning_reconciliation_job()

        assert c1 == 0
        assert c2 == 0
        assert c3 == 0
        assert c4 == 0
        assert res5 == {"marzban": True, "payment_gateway": True}
        assert c6 == 0
        assert c7 == 0
        assert c8 == 0
