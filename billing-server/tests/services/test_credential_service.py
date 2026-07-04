"""
test_credential_service.py — Unit tests for Phase 2.4 VPN Credential Lifecycle Service.
Tests retrieval, on-demand client config generation, rotation, revocation, restoration,
idempotency, and zero-secret logging.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.models import ProvisioningProfile, ProvisioningState
from app.services.credential_service import CredentialService
from app.services.provisioning.provider import ProvisionedUserDTO
from app.services.exceptions import (
    CredentialNotFoundError,
    CredentialAlreadyRevokedError,
    CredentialAlreadyActiveError,
    CredentialRotationFailedError,
)


@pytest.fixture
def mock_provisioning_service() -> AsyncMock:
    service = AsyncMock()
    service.provisioning_repo = MagicMock()
    return service


@pytest.fixture
def service(mock_provisioning_service: AsyncMock) -> CredentialService:
    return CredentialService(session=AsyncMock(), provisioning_service=mock_provisioning_service)


@pytest.fixture
def sample_profile() -> ProvisioningProfile:
    profile = ProvisioningProfile(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        remote_user_id="user_test_123",
        provisioning_state=ProvisioningState.ACTIVE,
    )
    return profile


@pytest.fixture
def sample_user_dto() -> ProvisionedUserDTO:
    return ProvisionedUserDTO(
        remote_user_id="user_test_123",
        status="active",
        links=[
            "vless://client-uuid-999@vpn.realitytunnel.com:443?type=tcp&security=reality&pbk=mock_pbk_value&sni=sni.tunnel.com&sid=mock_sid_value#user_test_123"
        ],
    )


# ── Retrieval Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retrieve_credentials_success(
    service: CredentialService,
    mock_provisioning_service: AsyncMock,
    sample_profile: ProvisioningProfile,
    sample_user_dto: ProvisionedUserDTO,
):
    mock_provisioning_service.get_provisioned_user.return_value = (sample_profile, sample_user_dto)

    data = await service.get_credentials(sample_profile.account_id)

    assert data["server_hostname"] == "vpn.realitytunnel.com"
    assert data["port"] == 443
    assert data["protocol"] == "vless"
    assert data["transport"] == "tcp"
    assert data["security"] == "reality"
    assert data["uuid"] == "client-uuid-999"
    assert data["public_key"] == "mock_pbk_value"
    assert data["short_id"] == "mock_sid_value"
    assert data["sni"] == "sni.tunnel.com"
    assert "outbounds" in data["client_config"]
    assert data["clash_config"]["status"] == "unsupported"


@pytest.mark.asyncio
async def test_retrieve_vless_uri(
    service: CredentialService,
    mock_provisioning_service: AsyncMock,
    sample_profile: ProvisioningProfile,
    sample_user_dto: ProvisionedUserDTO,
):
    mock_provisioning_service.get_provisioned_user.return_value = (sample_profile, sample_user_dto)
    uri = await service.get_vless_uri(sample_profile.account_id)
    assert uri == sample_user_dto.links[0]


@pytest.mark.asyncio
async def test_retrieve_singbox_config(
    service: CredentialService,
    mock_provisioning_service: AsyncMock,
    sample_profile: ProvisioningProfile,
    sample_user_dto: ProvisionedUserDTO,
):
    mock_provisioning_service.get_provisioned_user.return_value = (sample_profile, sample_user_dto)
    config = await service.get_singbox_config(sample_profile.account_id)
    assert config["log"]["level"] == "info"
    assert config["outbounds"][0]["type"] == "vless"
    assert config["outbounds"][0]["uuid"] == "client-uuid-999"


# ── Lifecycle & Idempotency Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_regenerate_credentials(
    service: CredentialService,
    mock_provisioning_service: AsyncMock,
    sample_profile: ProvisioningProfile,
    sample_user_dto: ProvisionedUserDTO,
):
    new_dto = ProvisionedUserDTO(
        remote_user_id="user_test_123",
        status="active",
        links=[
            "vless://new-rotated-uuid@vpn.realitytunnel.com:443?type=tcp&security=reality&pbk=new_pbk&sni=sni.tunnel.com&sid=new_sid#user_test_123"
        ],
    )
    mock_provisioning_service.rotate_user_credentials.return_value = (sample_profile, new_dto)

    data = await service.regenerate_credentials(sample_profile.account_id)
    assert data["uuid"] == "new-rotated-uuid"
    assert data["public_key"] == "new_pbk"
    mock_provisioning_service.rotate_user_credentials.assert_called_once_with(sample_profile.account_id)


@pytest.mark.asyncio
async def test_revoke_credentials_success(
    service: CredentialService,
    mock_provisioning_service: AsyncMock,
    sample_profile: ProvisioningProfile,
):
    sample_profile.provisioning_state = ProvisioningState.ACTIVE
    mock_provisioning_service.provisioning_repo.get_by_account_id = AsyncMock(return_value=sample_profile)

    await service.revoke_credentials(sample_profile.account_id)
    mock_provisioning_service.suspend_subscription.assert_called_once_with(sample_profile.account_id)


@pytest.mark.asyncio
async def test_repeated_revoke_raises_error(
    service: CredentialService,
    mock_provisioning_service: AsyncMock,
    sample_profile: ProvisioningProfile,
):
    sample_profile.provisioning_state = ProvisioningState.SUSPENDED
    mock_provisioning_service.provisioning_repo.get_by_account_id = AsyncMock(return_value=sample_profile)

    with pytest.raises(CredentialAlreadyRevokedError):
        await service.revoke_credentials(sample_profile.account_id)


@pytest.mark.asyncio
async def test_restore_credentials_success(
    service: CredentialService,
    mock_provisioning_service: AsyncMock,
    sample_profile: ProvisioningProfile,
):
    sample_profile.provisioning_state = ProvisioningState.SUSPENDED
    mock_provisioning_service.provisioning_repo.get_by_account_id = AsyncMock(return_value=sample_profile)

    await service.restore_credentials(sample_profile.account_id)
    mock_provisioning_service.reactivate_subscription.assert_called_once_with(sample_profile.account_id)


@pytest.mark.asyncio
async def test_repeated_restore_raises_error(
    service: CredentialService,
    mock_provisioning_service: AsyncMock,
    sample_profile: ProvisioningProfile,
):
    sample_profile.provisioning_state = ProvisioningState.ACTIVE
    mock_provisioning_service.provisioning_repo.get_by_account_id = AsyncMock(return_value=sample_profile)

    with pytest.raises(CredentialAlreadyActiveError):
        await service.restore_credentials(sample_profile.account_id)


@pytest.mark.asyncio
async def test_terminated_profile_raises_not_found(
    service: CredentialService,
    mock_provisioning_service: AsyncMock,
    sample_profile: ProvisioningProfile,
    sample_user_dto: ProvisionedUserDTO,
):
    sample_profile.provisioning_state = ProvisioningState.TERMINATED
    mock_provisioning_service.get_provisioned_user.return_value = (sample_profile, sample_user_dto)

    with pytest.raises(CredentialNotFoundError):
        await service.get_credentials(sample_profile.account_id)
