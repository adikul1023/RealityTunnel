"""
Health router — GET /health, /livez, /readyz, /admin/health (Phase 3.1 & 3.2.8).

Verifies:
  - /livez: Pure liveness probe (0 DB queries, instant response).
  - /health: Public status contract (same as /livez).
  - /readyz: Readiness probe (verifies database connectivity).
  - /admin/health: Deep diagnostics (authenticated).
"""
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, verify_db
from app.dependencies import get_current_admin
from app.repositories import ProvisioningRetryRepository, SystemHealthRepository
from app.core.fingerprint import compute_configuration_fingerprint
from app.observability.metrics import metrics_registry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


class BasicHealthResponse(BaseModel):
    status: str
    version: str | None = None


class ReadyResponse(BaseModel):
    status: str
    database: str


class ComponentStatus(BaseModel):
    status: str           # "ok" | "degraded" | "error"
    latency_ms: float | None = None
    detail: str | None = None


class AdminHealthResponse(BaseModel):
    status: str
    database: dict[str, Any] | str | None = None
    version: str | None = None
    git_commit: str | None = None
    build_date: str | None = None
    docker_image: str | None = None
    components: dict[str, ComponentStatus] | None = None
    fingerprint: dict[str, Any] | None = None
    scheduler: dict[str, Any] | None = None
    retry_queue: dict[str, Any] | None = None
    provider_health: dict[str, Any] | None = None
    metrics_summary: dict[str, Any] | None = None
    backups: dict[str, Any] | None = None
    security: dict[str, Any] | None = None
    performance: dict[str, Any] | None = None


@router.get(
    "/livez",
    summary="Liveness probe",
    response_model=BasicHealthResponse,
)
async def livez() -> BasicHealthResponse:
    """
    Pure liveness probe. Indicates the ASGI server is accepting connections.
    Does not access the database. Immune to DB connection exhaustion.
    """
    return BasicHealthResponse(status="ok", version=settings.app_version)


@router.get(
    "/health",
    summary="Public health status",
    response_model=BasicHealthResponse,
)
async def health_check() -> BasicHealthResponse:
    """
    Public API health contract. Identical to /livez.
    """
    return BasicHealthResponse(status="ok", version=settings.app_version)


@router.get(
    "/readyz",
    summary="Readiness probe",
    response_model=ReadyResponse,
)
async def readyz() -> ReadyResponse:
    """
    Readiness probe. Checks if the application is ready to serve traffic
    by performing a lightweight connectivity check against the database.
    Designed for orchestrators (e.g. Kubernetes, Docker HEALTHCHECK).
    """
    try:
        await verify_db()
        return ReadyResponse(status="ok", database="ok")
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "database": "unreachable"}
        )


@router.get(
    "/api/admin/system-health",
    summary="Deep diagnostics health check",
    response_model=AdminHealthResponse,
    dependencies=[Depends(get_current_admin)],
)
async def admin_health(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> AdminHealthResponse:
    """
    Fully authenticated deep diagnostics endpoint.
    Aggregates database latency, background component statuses, configuration fingerprints,
    scheduler jobs, retry queues, and security metrics.
    """
    components: dict[str, ComponentStatus] = {}
    overall_ok = True

    # ── PostgreSQL ───────────────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        await verify_db()
        pg_latency = round((time.perf_counter() - t0) * 1000, 2)
        components["postgresql"] = ComponentStatus(
            status="ok", latency_ms=pg_latency
        )
        db_status = {"status": "ok", "latency_ms": pg_latency}
    except Exception as exc:
        pg_latency = round((time.perf_counter() - t0) * 1000, 2)
        logger.error("Admin health check — PostgreSQL unreachable: %s", exc)
        components["postgresql"] = ComponentStatus(
            status="error",
            latency_ms=pg_latency,
            detail=str(exc),
        )
        db_status = {"status": "error", "latency_ms": pg_latency, "detail": str(exc)}
        overall_ok = False

    # ── Background Monitored Components (Marzban & Payment Gateway) ──────
    external_degraded = False
    if components["postgresql"].status == "ok":
        try:
            repo = SystemHealthRepository(session)
            statuses = await repo.get_all_statuses()
            monitored = {s.component_key: s for s in statuses}
            for key in ("marzban", "payment_gateway"):
                if key in monitored:
                    rec = monitored[key]
                    components[key] = ComponentStatus(
                        status=rec.status,
                        detail=rec.message,
                    )
                    if rec.status != "ok":
                        external_degraded = False if rec.status == "ok" else True
                else:
                    components[key] = ComponentStatus(
                        status="ok",
                        detail="Not checked yet by background monitor",
                    )
        except Exception as exc:
            logger.warning("Failed to retrieve background system health statuses: %s", exc)
            for key in ("marzban", "payment_gateway"):
                components[key] = ComponentStatus(status="ok", detail="Health query failed")

    status_str = "ok"
    if not overall_ok:
        status_str = "error"
    elif external_degraded:
        status_str = "degraded"

    response_kwargs: dict[str, Any] = {
        "status": status_str,
        "database": db_status,
        "version": settings.app_version,
        "git_commit": getattr(settings, "git_commit", "unknown"),
        "build_date": getattr(settings, "build_date", "unknown"),
        "docker_image": getattr(settings, "docker_image", "billing-server-billing-api:latest"),
        "components": components,
        "fingerprint": compute_configuration_fingerprint(),
    }

    if hasattr(request.app.state, "scheduler") and request.app.state.scheduler:
        response_kwargs["scheduler"] = {
            "status": "running" if getattr(request.app.state.scheduler, "_running", False) else "stopped",
            "jobs": request.app.state.scheduler.get_job_stats(),
        }
    else:
        response_kwargs["scheduler"] = {"status": "not_initialized", "jobs": {}}

    try:
        retry_repo = ProvisioningRetryRepository(session)
        pending_cnt = await retry_repo.count_total("pending")
        failed_cnt = await retry_repo.count_total("failed")
        response_kwargs["retry_queue"] = {"pending": pending_cnt, "failed": failed_cnt}
    except Exception:
        response_kwargs["retry_queue"] = {"pending": 0, "failed": 0, "error": "query_failed"}

    response_kwargs["provider_health"] = {
        "marzban": components.get("marzban", ComponentStatus(status="ok")).status,
        "payment_gateway": components.get("payment_gateway", ComponentStatus(status="ok")).status,
    }
    response_kwargs["metrics_summary"] = metrics_registry.get_summary()

    try:
        from app.recovery.backup import BackupService
        from app.recovery.integrity import get_verification_state
        from datetime import datetime, timezone
        backup_srv = BackupService()
        stored = backup_srv.list_backups()
        backup_count = len(stored)
        latest_age = None
        if stored and "created_at" in stored[0]:
            try:
                ts_str = str(stored[0]["created_at"])
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                created_dt = datetime.fromisoformat(ts_str)
                latest_age = round((datetime.now(timezone.utc) - created_dt).total_seconds(), 1)
            except Exception:
                pass
        ver_state = get_verification_state(backup_srv.backup_dir)
        response_kwargs["backups"] = {
            "count": backup_count,
            "latest_backup_age": latest_age,
            "last_successful_verification": ver_state.get("last_successful_verification"),
            "last_failed_verification": ver_state.get("last_failed_verification"),
        }
    except Exception as exc:
        logger.warning("Failed to retrieve backup recovery health: %s", exc)
        response_kwargs["backups"] = {
            "count": 0,
            "latest_backup_age": None,
            "last_successful_verification": None,
            "last_failed_verification": None,
            "error": str(exc),
        }

    try:
        from app.security_hardening.rotation import secret_rotation_service
        from app.security_hardening.audit import audit_service
        rot_status = secret_rotation_service.get_rotation_status()
        audit_status = await audit_service.get_queue_status()
        response_kwargs["security"] = {
            "current_signing_key_generation": rot_status.get("current_signing_key_generation"),
            "active_secret_generations": rot_status.get("active_secret_generations"),
            "rotation_status": rot_status.get("rotation_status"),
            "audit_queue_status": audit_status,
        }
    except Exception as exc:
        logger.warning("Failed to retrieve security hardening health: %s", exc)
        response_kwargs["security"] = {
            "current_signing_key_generation": None,
            "active_secret_generations": {},
            "rotation_status": "error",
            "audit_queue_status": {"error": str(exc)},
        }

    try:
        from app.performance.pooling import get_pool_status
        from app.performance.profiler import profiler
        from app.performance.cache import get_cache
        pool_status = get_pool_status()
        cache_status = await get_cache().get_stats()
        endpoint_pcts = profiler.get_category_percentiles("endpoint")
        res_usage = profiler.get_resource_usage()
        response_kwargs["performance"] = {
            "database_pool_usage": pool_status.get("checked_out", 0),
            "database_pool_status": pool_status,
            "cache_statistics": cache_status,
            "average_endpoint_latency_ms": endpoint_pcts.get("avg", 0.0),
            "p95_latency_ms": endpoint_pcts.get("p95", 0.0),
            "scheduler_utilization": response_kwargs.get("scheduler", {}),
            "memory_usage_bytes": res_usage.get("memory_usage_bytes", 0),
            "cpu_usage_percent": res_usage.get("cpu_usage_percent", 0.0),
        }
    except Exception as exc:
        logger.warning("Failed to retrieve performance health: %s", exc)
        response_kwargs["performance"] = {"error": str(exc)}

    response = AdminHealthResponse(**response_kwargs)

    if not overall_ok:
        raise HTTPException(status_code=503, detail=response.model_dump())

    return response
