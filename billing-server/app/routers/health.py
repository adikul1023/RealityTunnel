"""
Health router — GET /health

Verifies:
  - Service is reachable (trivially true if the endpoint responds)
  - PostgreSQL is reachable and responds to SELECT 1
"""
import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import verify_db

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
async def health_check() -> HealthResponse:
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

    response = HealthResponse(
        status="ok" if overall_ok else "degraded",
        components=components,
    )

    if not overall_ok:
        raise HTTPException(status_code=503, detail=response.model_dump())

    return response
