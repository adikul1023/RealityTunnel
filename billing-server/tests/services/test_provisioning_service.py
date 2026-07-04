"""
test_provisioning_service.py — Comprehensive unit tests for Phase 2.2 VPN Provisioning Domain.
Tests Marzban provider exception translation, retries, timeouts, and ProvisioningService orchestration,
idempotency, and row-level locking without requiring a live Marzban instance.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, ProvisioningProfile, ProvisioningState
from app.repositories import AccountRepository
from app.services import (
    ProvisioningService,
    ProvisionedUserDTO,
    MarzbanProvisioningProvider,
    ProvisioningServiceError,
    ProvisioningProviderError,
    ProvisioningConflictError,
    ProvisioningUnavailableError,
    ProvisioningSynchronizationError,
    ProvisioningTimeoutError,
)


@pytest.fixture
async def test_account(db_session: AsyncSession) -> Account:
    repo = AccountRepository(db_session)
    account = await repo.create(
        account_id="PROV-TEST-001",
        master_token_hash="provhash" * 8,
        plan_id="pro",
    )
    return account


@pytest.fixture
def mock_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.create_user.return_value = ProvisionedUserDTO(
        remote_user_id="user_prov_test_001",
        status="active",
        links=["vless://test-secret-link"],
    )
    provider.update_user.return_value = ProvisionedUserDTO(
        remote_user_id="user_prov_test_001",
        status="active",
        links=["vless://test-secret-link"],
    )
    provider.suspend_user.return_value = ProvisionedUserDTO(
        remote_user_id="user_prov_test_001",
        status="disabled",
        links=[],
    )
    provider.unsuspend_user.return_value = ProvisionedUserDTO(
        remote_user_id="user_prov_test_001",
        status="active",
        links=["vless://test-secret-link"],
    )
    provider.delete_user.return_value = True
    provider.get_user.return_value = ProvisionedUserDTO(
        remote_user_id="user_prov_test_001",
        status="active",
        links=["vless://test-secret-link"],
    )
    provider.sync_user.return_value = ProvisionedUserDTO(
        remote_user_id="user_prov_test_001",
        status="active",
        links=["vless://test-secret-link"],
    )
    return provider


@pytest.fixture
def service(db_session: AsyncSession, mock_provider: AsyncMock) -> ProvisioningService:
    return ProvisioningService(db_session, mock_provider)


# ── 1. Marzban Provider HTTP Translation & Retries ──────────────────────────


@pytest.mark.asyncio
async def test_marzban_provider_success():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "username": "test_remote_user",
        "status": "active",
        "data_limit": 1073741824,
        "data_used": 1024,
        "expire": 1735689600,
        "links": ["vless://secret"],
    }
    mock_client.request.return_value = mock_response

    provider = MarzbanProvisioningProvider(base_url="http://mock", client=mock_client)
    dto = await provider.create_user("test_remote_user", data_limit=1073741824)

    assert dto.remote_user_id == "test_remote_user"
    assert dto.status == "active"
    assert dto.data_limit == 1073741824
    assert dto.data_used == 1024
    assert dto.expire_at == 1735689600
    assert dto.links == ["vless://secret"]


@pytest.mark.asyncio
async def test_marzban_provider_conflict():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 409
    mock_client.request.return_value = mock_response

    provider = MarzbanProvisioningProvider(base_url="http://mock", client=mock_client)
    with pytest.raises(ProvisioningConflictError):
        await provider.create_user("duplicate_user")


@pytest.mark.asyncio
async def test_marzban_provider_timeout_with_retries():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request.side_effect = httpx.TimeoutException("Connection timed out")

    provider = MarzbanProvisioningProvider(base_url="http://mock", max_retries=2, client=mock_client)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(ProvisioningTimeoutError):
            await provider.create_user("timeout_user")

    assert mock_client.request.call_count == 2


@pytest.mark.asyncio
async def test_marzban_provider_unavailable_with_retries():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 503
    mock_client.request.return_value = mock_response

    provider = MarzbanProvisioningProvider(base_url="http://mock", max_retries=3, client=mock_client)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(ProvisioningUnavailableError):
            await provider.create_user("unavailable_user")

    assert mock_client.request.call_count == 3


# ── 2. ProvisioningService Orchestration & Idempotency ──────────────────────


@pytest.mark.asyncio
async def test_provision_subscription_success(
    service: ProvisioningService, test_account: Account, mock_provider: AsyncMock
):
    profile = await service.provision_subscription(test_account.id, plan_id="pro")

    assert profile.account_id == test_account.id
    assert profile.provisioning_state == ProvisioningState.ACTIVE
    assert profile.remote_user_id == "user_prov_test_001"
    assert profile.last_error is None
    assert test_account.marzban_username == "user_prov_test_001"
    mock_provider.create_user.assert_called_once()


@pytest.mark.asyncio
async def test_provision_subscription_idempotency(
    service: ProvisioningService, test_account: Account, mock_provider: AsyncMock
):
    # First provision
    profile1 = await service.provision_subscription(test_account.id, plan_id="pro")
    assert mock_provider.create_user.call_count == 1

    # Second provision on already active account should not create user again
    profile2 = await service.provision_subscription(test_account.id, plan_id="pro")
    assert mock_provider.create_user.call_count == 1
    assert profile2.id == profile1.id
    assert profile2.provisioning_state == ProvisioningState.ACTIVE


@pytest.mark.asyncio
async def test_suspend_and_reactivate(
    service: ProvisioningService, test_account: Account, mock_provider: AsyncMock
):
    await service.provision_subscription(test_account.id, plan_id="pro")

    suspended = await service.suspend_subscription(test_account.id)
    assert suspended.provisioning_state == ProvisioningState.SUSPENDED
    mock_provider.suspend_user.assert_called_once_with("user_prov_test_001")

    reactivated = await service.reactivate_subscription(test_account.id)
    assert reactivated.provisioning_state == ProvisioningState.ACTIVE
    mock_provider.unsuspend_user.assert_called_once_with("user_prov_test_001")


@pytest.mark.asyncio
async def test_idempotent_suspend_and_delete(
    service: ProvisioningService, test_account: Account, mock_provider: AsyncMock
):
    await service.provision_subscription(test_account.id, plan_id="pro")

    # First suspend
    await service.suspend_subscription(test_account.id)
    assert mock_provider.suspend_user.call_count == 1

    # Second suspend should be idempotent and not call provider again
    await service.suspend_subscription(test_account.id)
    assert mock_provider.suspend_user.call_count == 1

    # First terminate
    term1 = await service.terminate_subscription(test_account.id)
    assert term1 is not None
    assert term1.provisioning_state == ProvisioningState.TERMINATED
    assert mock_provider.delete_user.call_count == 1

    # Second terminate should be idempotent
    term2 = await service.terminate_subscription(test_account.id)
    assert term2 is not None
    assert term2.provisioning_state == ProvisioningState.TERMINATED
    assert mock_provider.delete_user.call_count == 1


@pytest.mark.asyncio
async def test_sync_failures_recorded(
    service: ProvisioningService, test_account: Account, mock_provider: AsyncMock
):
    await service.provision_subscription(test_account.id, plan_id="pro")

    mock_provider.sync_user.side_effect = ProvisioningProviderError("Remote API failed")

    with pytest.raises(ProvisioningSynchronizationError):
        await service.synchronize(test_account.id)


@pytest.mark.asyncio
async def test_concurrency_row_locking(
    service: ProvisioningService, test_account: Account
):
    with patch.object(
        service.provisioning_repo, "get_by_account_id", wraps=service.provisioning_repo.get_by_account_id
    ) as mock_get:
        await service.provision_subscription(test_account.id, plan_id="pro")
        mock_get.assert_called_with(test_account.id, for_update=True)
