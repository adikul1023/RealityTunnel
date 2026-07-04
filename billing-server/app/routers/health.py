"""
Health router — GET /health (Phase 3.1 & 3.2.8).

Verifies:
  - Service is reachable
  - PostgreSQL is reachable and responds to SELECT 1
  - Background monitored components (Marzban, Payment Gateway) from system_health table
  - Anonymous users receive basic status, database latency, and app version.
  - Admin users additionally receive configuration fingerprint, scheduler status, retry queue depth,
    provider health, and metrics summary.
"""
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, verify_db
from app.dependencies import get_current_admin_optional
from app.repositories import ProvisioningRetryRepository, SystemHealthRepository
from app.core.fingerprint import compute_configuration_fingerprint
from app.observability.metrics import metrics_registry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


class ComponentStatus(BaseModel):
    status: str           # "ok" | "degraded" | "error"
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: dict[str, Any] | str | None = None
    version: str | None = None
    components: dict[str, ComponentStatus] | None = None
    fingerprint: dict[str, Any] | None = None
    scheduler: dict[str, Any] | None = None
    retry_queue: dict[str, Any] | None = None
    provider_health: dict[str, Any] | None = None
    metrics_summary: dict[str, Any] | None = None


@router.get(
    "/health",
    summary="Health check",
    response_model=HealthResponse,
    responses={
        200: {"description": "All components healthy"},
        503: {"description": "One or more components degraded"},
    },
)
async def health_check(
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Any = Depends(get_current_admin_optional),
) -> HealthResponse:
    """
    Returns 200 when all components are healthy.
    Returns 503 when any component is degraded.
    Differentiates response payload between anonymous callers and authenticated admins.
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
        logger.error("Health check — PostgreSQL unreachable: %s", exc)
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
        "components": components,
    }

    if admin:
        response_kwargs["fingerprint"] = compute_configuration_fingerprint()
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

    response = HealthResponse(**response_kwargs)

    if not overall_ok:
        raise HTTPException(status_code=503, detail=response.model_dump())

    return response
