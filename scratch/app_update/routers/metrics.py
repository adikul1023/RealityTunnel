"""
metrics.py — GET /metrics Prometheus Export Router (Phase 3.2.6).

Exposes standard Prometheus `# HELP`, `# TYPE`, and text formatted metrics.
Supports optional Admin authentication when configured via `metrics_auth_required`.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.config import settings
from app.dependencies import get_current_admin_optional
from app.observability import metrics_registry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Observability"])


@router.get(
    "/metrics",
    summary="Prometheus metrics export",
    response_class=Response,
    responses={
        200: {"description": "Prometheus formatted text metrics"},
        401: {"description": "Authentication required when metrics_auth_required is True"},
    },
)
async def get_metrics(
    admin: Any = Depends(get_current_admin_optional),
) -> Response:
    """
    Export metrics in standard Prometheus text format (version 0.0.4).
    Never exposes internal secrets or credentials.
    """
    if getattr(settings, "metrics_auth_required", False) and not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for metrics endpoint",
        )

    return Response(
        content=metrics_registry.to_prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
