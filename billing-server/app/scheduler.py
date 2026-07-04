"""
scheduler.py — Native asyncio background job scheduler for OverREALITY lifecycle automation.
Orchestrates periodic execution of LifecycleJobService methods with explicit error isolation
and clean lifecycle integration (startup/shutdown).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dependencies import get_marzban_provider, get_razorpay_provider
from app.services import (
    CredentialService,
    LifecycleJobService,
    PaymentService,
    ProvisioningService,
    SubscriptionService,
)

logger = logging.getLogger(__name__)


class JobScheduler:
    """
    Async background job scheduler for RealityTunnel lifecycle automation.
    Manages periodic tasks with explicit intervals and error isolation.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def _execute_job(self, job_name: str, method_name: str) -> Any:
        try:
            async with self.session_factory() as session:
                marzban_provider = get_marzban_provider()
                razorpay_provider = get_razorpay_provider()
                provisioning_service = ProvisioningService(session, marzban_provider)
                credential_service = CredentialService(session, provisioning_service)
                provisioning_service.credential_service = credential_service
                subscription_service = SubscriptionService(session, provisioning_service=provisioning_service)
                payment_service = PaymentService(session, razorpay_provider, subscription_service)
                job_service = LifecycleJobService(
                    session,
                    subscription_service,
                    provisioning_service,
                    payment_service,
                    credential_service,
                )
                func = getattr(job_service, method_name)
                result = await func()
                logger.info("Job %s completed successfully: %s", job_name, result)
                return result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Job %s failed with error: %s", job_name, str(exc), exc_info=True)
            return None

    async def _loop_job(self, name: str, interval_seconds: int, method_name: str) -> None:
        logger.info("Starting background job loop '%s' with interval %ds", name, interval_seconds)
        while self._running:
            try:
                await self._execute_job(name, method_name)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Unexpected error in job loop '%s': %s", name, str(exc), exc_info=True)
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
        logger.info("Stopped background job loop '%s'", name)

    def start(self) -> None:
        """Start all background job tasks."""
        if self._running:
            return
        self._running = True
        logger.info("JobScheduler starting up...")
        jobs = [
            ("failed_provision_retry", 60, "run_failed_provision_retry_job"),
            ("system_health_monitoring", 300, "run_system_health_monitoring_job"),
            ("subscription_expiration", 600, "run_subscription_expiration_job"),
            ("grace_period_expiration", 600, "run_grace_period_expiration_job"),
            ("stale_pending_payment_cleanup", 1800, "run_stale_pending_payment_cleanup_job"),
            ("orphan_provisioning_cleanup", 3600, "run_orphan_provisioning_cleanup_job"),
            ("credential_rotation", 86400, "run_credential_rotation_job"),
        ]
        for name, interval, method_name in jobs:
            task = asyncio.create_task(self._loop_job(name, interval, method_name), name=name)
            self._tasks.append(task)
        logger.info("JobScheduler started %d tasks.", len(self._tasks))

    async def stop(self) -> None:
        """Gracefully stop and cancel all running background tasks."""
        if not self._running:
            return
        logger.info("JobScheduler shutting down...")
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("JobScheduler shutdown complete.")
