"""
app/observability/middleware.py — Request Timing & Correlation Middleware (Phase 3.2.2, 3.2.4, 3.2.9).
FastAPI/Starlette middleware that passively injects correlation IDs, tracks request duration,
detects slow requests, records HTTP metrics, and ensures response headers include timing and correlation data.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.config import settings
from app.observability.context import bind_context, reset_context
from app.observability.metrics import metrics_registry
from app.observability.tracing import get_tracer

logger = logging.getLogger(__name__)


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Passive HTTP observability middleware.
    Manages request correlation IDs, duration measurement, active/total request metrics,
    slow request detection, and X-Request-ID / X-Response-Time response headers.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract or generate Request ID
        req_id = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
        if not req_id or not req_id.strip():
            req_id = str(uuid.uuid4())
        else:
            req_id = req_id.strip()

        corr_id = request.headers.get("X-Correlation-ID") or request.headers.get("x-correlation-id") or req_id

        method = request.method
        path = request.url.path
        route_label = path

        # Bind contextvars
        tokens = bind_context(
            request_id=req_id,
            correlation_id=corr_id,
            component="http",
            operation=f"{method} {path}",
        )

        start_time = time.perf_counter()
        labels = {"method": method, "route": route_label}
        metrics_registry.inc_gauge("http_requests_active", 1.0, labels)

        status_code = 500
        response: Response | None = None

        try:
            with get_tracer().start_span(f"HTTP {method} {path}", {"http.method": method, "http.url": path}) as span:
                response = await call_next(request)
                status_code = response.status_code
                span.set_attribute("http.status_code", status_code)
                return response
        except Exception as exc:
            status_code = 500
            record_exception_metric(exc, request, status_code)
            raise
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            metrics_registry.inc_gauge("http_requests_active", -1.0, labels)

            status_str = str(status_code)
            metric_labels = {"method": method, "route": route_label, "status": status_str}
            metrics_registry.inc_counter("http_requests_total", 1.0, metric_labels)
            metrics_registry.observe("http_request_duration_ms", duration_ms, labels)

            if status_code >= 400:
                metrics_registry.inc_counter("http_errors_total", 1.0, metric_labels)

            if response is not None:
                response.headers["X-Request-ID"] = req_id
                response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

            # Check for slow requests (Phase 3.2.9)
            threshold = getattr(settings, "slow_request_threshold_ms", 500.0)
            if duration_ms > threshold:
                logger.warning(
                    "Slow request detected: %s %s took %.2fms (threshold %.2fms)",
                    method,
                    path,
                    duration_ms,
                    threshold,
                    extra={
                        "duration_ms": duration_ms,
                        "status": status_code,
                        "request_id": req_id,
                        "correlation_id": corr_id,
                        "force_sample": True,
                    },
                )
            else:
                logger.info(
                    "HTTP request completed",
                    extra={
                        "duration_ms": duration_ms,
                        "status": status_code,
                        "request_id": req_id,
                        "correlation_id": corr_id,
                    },
                )

            reset_context(tokens)


def record_exception_metric(exc: Exception, request: Request, status_code: int) -> None:
    """Passively record exception metrics (Phase 3.2.10) without storing exception messages."""
    try:
        exc_type = type(exc).__name__
        endpoint = request.url.path
        labels = {
            "exception_type": exc_type,
            "endpoint": endpoint,
            "http_status": str(status_code),
        }
        metrics_registry.inc_counter("exceptions_total", 1.0, labels)
    except Exception:
        pass
