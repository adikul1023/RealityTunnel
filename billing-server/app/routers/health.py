"""
Health router — GET /health

Verifies:
  - Service is reachable (trivially true if the endpoint responds)
  - PostgreSQL is reachable and responds to SELECT 1
  - Background monitored components (Marzban, Payment Gateway) from system_health table
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, verify_db
from app.repositories import SystemHealthRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


class ComponentStatus(BaseModel):
    status: str           # "ok" | "degraded" | "error"
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str           # "ok" | "degraded"
    components: dict[str, ComponentStatus]


@router.get(
    "/health",
    summary="Health check",
    response_model=HealthResponse,
    responses={
        200: {"description": "All components healthy"},
        503: {"description": "One or more components degraded"},
    },
)
async def health_check(session: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Returns 200 when all components are healthy.
    Returns 503 when any component is degraded.

    Always returns a structured JSON body so callers can inspect
    individual component status.
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
    except Exception as exc:
        pg_latency = round((time.perf_counter() - t0) * 1000, 2)
        logger.error("Health check — PostgreSQL unreachable: %s", exc)
        components["postgresql"] = ComponentStatus(
            status="error",
            latency_ms=pg_latency,
            detail=str(exc),
        )
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

    response = HealthResponse(
        status=status_str,
        components=components,
    )

    if not overall_ok:
        raise HTTPException(status_code=503, detail=response.model_dump())

    return response

