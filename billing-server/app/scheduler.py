"""
scheduler.py — Native asyncio background job scheduler for OverREALITY lifecycle automation.
Orchestrates periodic execution of LifecycleJobService methods with explicit error isolation,
clean lifecycle integration, correlation context injection, OpenTelemetry tracing, and metric reporting.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dependencies import get_marzban_provider, get_razorpay_provider
from app.observability import bind_context, clear_context, get_tracer, metrics_registry
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
    Manages periodic tasks with explicit intervals, correlation IDs, OpenTelemetry spans, and error isolation.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._job_stats: dict[str, dict[str, Any]] = {}

    def get_job_stats(self) -> dict[str, Any]:
        """Return execution statistics for all registered jobs."""
        return dict(self._job_stats)

    async def _execute_job(self, job_name: str, method_name: str) -> Any:
        if job_name not in self._job_stats:
            self._job_stats[job_name] = {
                "execution_count": 0,
                "execution_time_ms": 0.0,
                "failures": 0,
                "last_success": None,
                "last_failure": None,
            }
        stats = self._job_stats[job_name]

        job_req_id = f"job-{job_name}-{uuid.uuid4().hex[:8]}"
        tokens = bind_context(
            request_id=job_req_id,
            correlation_id=job_req_id,
            component="scheduler",
            operation=job_name,
        )
        t0 = time.perf_counter()

        try:
            with get_tracer().start_span(f"job.{job_name}", {"job.name": job_name}) as span:
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

                    duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                    stats["execution_count"] += 1
                    stats["execution_time_ms"] = duration_ms
                    stats["last_success"] = datetime.now(timezone.utc).isoformat()

                    metrics_registry.inc_counter("scheduler_jobs_executed_total", 1.0, {"job": job_name, "status": "success"})
                    metrics_registry.observe("scheduler_job_duration_ms", duration_ms, {"job": job_name})
                    span.set_attribute("job.status", "success")

                    logger.info(
                        "Job %s completed successfully",
                        job_name,
                        extra={
                            "duration_ms": duration_ms,
                            "request_id": job_req_id,
                            "correlation_id": job_req_id,
                        },
                    )
                    return result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            stats["execution_count"] += 1
            stats["failures"] += 1
            stats["execution_time_ms"] = duration_ms
            stats["last_failure"] = datetime.now(timezone.utc).isoformat()

            metrics_registry.inc_counter("scheduler_jobs_executed_total", 1.0, {"job": job_name, "status": "failure"})
            metrics_registry.inc_counter("scheduler_job_failures_total", 1.0, {"job": job_name})
            metrics_registry.observe("scheduler_job_duration_ms", duration_ms, {"job": job_name})

            logger.error(
                "Job %s failed with error: %s",
                job_name,
                str(exc),
                exc_info=True,
                extra={
                    "duration_ms": duration_ms,
                    "request_id": job_req_id,
                    "correlation_id": job_req_id,
                    "force_sample": True,
                },
            )
            return None
        finally:
            clear_context()

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
            if name not in self._job_stats:
                self._job_stats[name] = {
                    "execution_count": 0,
                    "execution_time_ms": 0.0,
                    "failures": 0,
                    "last_success": None,
                    "last_failure": None,
                }
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
