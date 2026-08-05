import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, AccountStatus
from app.services.admin_account import AdminAccountService
from app.services.provisioning.service import ProvisioningService
from app.repositories import AccountRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository

@pytest.fixture
def mock_account_repo():
    return AsyncMock(spec=AccountRepository)

@pytest.fixture
def mock_refresh_repo():
    return AsyncMock(spec=RefreshTokenRepository)

@pytest.fixture
def mock_provisioning_service():
    return AsyncMock(spec=ProvisioningService)


def make_account(account_id: uuid.UUID, status: AccountStatus) -> MagicMock:
    """Build a mock Account without touching SQLAlchemy's constructor."""
    acct = MagicMock(spec=Account)
    acct.id = account_id
    acct.account_id = str(account_id)
    acct.status = status
    acct.deleted_at = None
    return acct


@pytest.mark.asyncio
async def test_delete_account(mock_account_repo, mock_refresh_repo, mock_provisioning_service):
    account_id = uuid.uuid4()
    account = make_account(account_id, AccountStatus.ACTIVE)

    updated_account = make_account(account_id, AccountStatus.DELETED)
    updated_account.deleted_at = datetime.now(timezone.utc)

    mock_account_repo.get_by_account_id.return_value = account
    mock_account_repo.update.return_value = updated_account

    service = AdminAccountService(
        account_repo=mock_account_repo,
        refresh_repo=mock_refresh_repo,
        provisioning_service=mock_provisioning_service
    )

    deleted = await service.delete_account(str(account_id))

    assert deleted.status == AccountStatus.DELETED
    assert deleted.deleted_at is not None
    mock_refresh_repo.revoke_all_for_account.assert_awaited_once_with(account.id)
    mock_provisioning_service.terminate_subscription.assert_awaited_once_with(account.id)


@pytest.mark.asyncio
async def test_delete_account_offline_provider(mock_account_repo, mock_refresh_repo, mock_provisioning_service):
    account_id = uuid.uuid4()
    account = make_account(account_id, AccountStatus.ACTIVE)

    updated_account = make_account(account_id, AccountStatus.DELETED)
    updated_account.deleted_at = datetime.now(timezone.utc)

    mock_account_repo.get_by_account_id.return_value = account
    mock_account_repo.update.return_value = updated_account
    mock_provisioning_service.terminate_subscription.side_effect = Exception("Marzban offline")

    service = AdminAccountService(
        account_repo=mock_account_repo,
        refresh_repo=mock_refresh_repo,
        provisioning_service=mock_provisioning_service
    )

    # The deletion must still succeed — provider errors are handled inside delete_account
    deleted = await service.delete_account(str(account_id))

    assert deleted.status == AccountStatus.DELETED
    mock_provisioning_service.terminate_subscription.assert_awaited_once_with(account.id)
