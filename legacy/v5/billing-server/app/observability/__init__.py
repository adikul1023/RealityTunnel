"""
app/observability/ — Production Observability & Monitoring package (Phase 3.2).
Provides passive observability: structured JSON logging, correlation context, metrics registry,
Prometheus export, timing middleware, and OpenTelemetry abstraction hooks.
"""
from app.observability.context import (
    get_request_id,
    set_request_id,
    get_correlation_id,
    set_correlation_id,
    get_component,
    set_component,
    get_operation,
    set_operation,
    bind_context,
    clear_context,
)
from app.observability.logging import StructuredJsonFormatter, LogSamplingFilter
from app.observability.metrics import metrics_registry, MetricsRegistry
from app.observability.middleware import RequestObservabilityMiddleware, record_exception_metric
from app.observability.tracing import get_tracer, TracerInterface, SpanInterface

__all__ = [
    "get_request_id",
    "set_request_id",
    "get_correlation_id",
    "set_correlation_id",
    "get_component",
    "set_component",
    "get_operation",
    "set_operation",
    "bind_context",
    "clear_context",
    "StructuredJsonFormatter",
    "LogSamplingFilter",
    "metrics_registry",
    "MetricsRegistry",
    "RequestObservabilityMiddleware",
    "record_exception_metric",
    "get_tracer",
    "TracerInterface",
    "SpanInterface",
]

