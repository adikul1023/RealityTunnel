"""
test_connection_signal.py — Service layer unit and integration tests for ConnectionSecuritySignal.

Phase 1.4.4: Verifies event recording, ordering, pagination, and domain error translation.
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import RepositoryError
from app.models.connection_signal import ConnectionEventType, ConnectionSignal
from app.repositories import ConnectionSignalRepository
from app.services import ConnectionSignalService
from app.services.exceptions import ConnectionSignalServiceError


@pytest.mark.asyncio
async def test_record_signal_success(db_session: AsyncSession, signal_service: ConnectionSignalService, account_factory):
    """Verify recording a signal persists correctly with auto-generated UUID and timestamp."""
    acc = await account_factory("SIG-UNIT-1")
    dev_guid = "dev-guid-101"
    signal = await signal_service.record_signal(
        account_id=acc.id,
        event_type=ConnectionEventType.LOGIN,
        success=True,
        device_guid=dev_guid,
        source_ip="192.168.1.1",
        user_agent="TestAgent/1.0",
    )

    assert signal.id is not None
    assert signal.account_id == acc.id
    assert signal.event_type == ConnectionEventType.LOGIN
    assert signal.success is True
    assert signal.device_guid == dev_guid
    assert signal.source_ip == "192.168.1.1"
    assert signal.user_agent == "TestAgent/1.0"
    assert signal.occurred_at is not None
    assert signal.occurred_at.tzinfo is not None


@pytest.mark.asyncio
async def test_get_recent_signals_ordering_and_pagination(db_session: AsyncSession, signal_service: ConnectionSignalService, account_factory):
    """Verify signals are returned ordered by occurred_at descending and honor pagination limits."""
    acc = await account_factory("SIG-UNIT-2")
    now = datetime.now(timezone.utc)

    # Insert 5 signals with increasing timestamps
    for i in range(5):
        await signal_service.record_signal(
            account_id=acc.id,
            event_type=ConnectionEventType.REFRESH,
            success=True,
            occurred_at=now + timedelta(minutes=i),
        )

    # Retrieve all 5
    signals = await signal_service.get_recent_signals(acc.id, limit=10)
    assert len(signals) == 5
    # Check ordering (newest first)
    assert signals[0].occurred_at > signals[-1].occurred_at

    # Check limit and offset
    page1 = await signal_service.get_recent_signals(acc.id, limit=2, offset=0)
    assert len(page1) == 2
    assert page1[0].id == signals[0].id
    assert page1[1].id == signals[1].id

    page2 = await signal_service.get_recent_signals(acc.id, limit=2, offset=2)
    assert len(page2) == 2
    assert page2[0].id == signals[2].id
    assert page2[1].id == signals[3].id


@pytest.mark.asyncio
async def test_get_recent_signals_for_device(db_session: AsyncSession, signal_service: ConnectionSignalService, account_factory):
    """Verify querying signals by device GUID."""
    acc = await account_factory("SIG-UNIT-3")
    dev_guid = "device-test-guid-888"
    await signal_service.record_signal(
        account_id=acc.id,
        event_type=ConnectionEventType.DEVICE_REGISTER,
        success=True,
        device_guid=dev_guid,
    )
    await signal_service.record_signal(
        account_id=acc.id,
        event_type=ConnectionEventType.DEVICE_RENAME,
        success=True,
        device_guid=dev_guid,
    )
    await signal_service.record_signal(
        account_id=acc.id,
        event_type=ConnectionEventType.LOGIN,
        success=True,
        device_guid="other-device",
    )

    dev_signals = await signal_service.get_recent_signals_for_device(dev_guid)
    assert len(dev_signals) == 2
    for s in dev_signals:
        assert s.device_guid == dev_guid


@pytest.mark.asyncio
async def test_error_translation_on_repository_failure():
    """Verify repository exceptions are translated to ConnectionSignalServiceError."""
    mock_repo = AsyncMock(spec=ConnectionSignalRepository)
    mock_repo.create.side_effect = RepositoryError("Mock DB failure")

    service = ConnectionSignalService(mock_repo)
    with pytest.raises(ConnectionSignalServiceError) as exc_info:
        await service.record_signal(
            account_id=uuid.uuid4(),
            event_type=ConnectionEventType.LOGIN,
            success=True,
        )
    assert "Database error recording connection signal" in str(exc_info.value)
