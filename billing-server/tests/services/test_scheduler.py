"""
test_scheduler.py — Unit tests for Phase 2.6 JobScheduler abstraction.
Verifies task loop creation, startup/shutdown lifecycle, and error isolation.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.scheduler import JobScheduler


@pytest.fixture
def mock_session_factory():
    factory = MagicMock()
    mock_session = AsyncMock()
    factory.return_value.__aenter__.return_value = mock_session
    return factory


@pytest.mark.asyncio
@patch("app.scheduler.LifecycleJobService")
async def test_scheduler_start_stop(mock_job_svc_class, mock_session_factory):
    scheduler = JobScheduler(mock_session_factory)
    assert not scheduler._running
    assert len(scheduler._tasks) == 0

    scheduler.start()
    assert scheduler._running
    assert len(scheduler._tasks) == 8

    # Let loop run a tiny bit
    await asyncio.sleep(0.01)

    await scheduler.stop()
    assert not scheduler._running
    assert len(scheduler._tasks) == 0


@pytest.mark.asyncio
@patch("app.scheduler.LifecycleJobService")
async def test_scheduler_start_when_already_running(mock_job_svc_class, mock_session_factory):
    scheduler = JobScheduler(mock_session_factory)
    scheduler.start()
    tasks_count = len(scheduler._tasks)

    scheduler.start()
    assert len(scheduler._tasks) == tasks_count

    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_execute_job_success(mock_session_factory):
    scheduler = JobScheduler(mock_session_factory)
    
    with patch("app.scheduler.LifecycleJobService") as mock_job_svc_class, \
         patch("app.scheduler.get_marzban_provider"), \
         patch("app.scheduler.get_razorpay_provider"):
        
        mock_instance = AsyncMock()
        mock_instance.run_subscription_expiration_job = AsyncMock(return_value=5)
        mock_job_svc_class.return_value = mock_instance

        res = await scheduler._execute_job("subscription_expiration", "run_subscription_expiration_job")
        assert res == 5
        mock_instance.run_subscription_expiration_job.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_execute_job_exception_isolation(mock_session_factory):
    scheduler = JobScheduler(mock_session_factory)
    
    with patch("app.scheduler.LifecycleJobService") as mock_job_svc_class, \
         patch("app.scheduler.get_marzban_provider"), \
         patch("app.scheduler.get_razorpay_provider"):
        
        mock_instance = AsyncMock()
        mock_instance.run_subscription_expiration_job = AsyncMock(side_effect=RuntimeError("Database boom"))
        mock_job_svc_class.return_value = mock_instance

        res = await scheduler._execute_job("subscription_expiration", "run_subscription_expiration_job")
        assert res is None
        mock_instance.run_subscription_expiration_job.assert_called_once()
