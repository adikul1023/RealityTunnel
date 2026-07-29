"""
app/observability/tracing.py — OpenTelemetry Abstraction Hooks (Phase 3.2.11).
Creates tracing abstraction interface only without requiring OpenTelemetry libraries.
Provides a zero-overhead No-Op default implementation so future exporters can plug in
without modifying domain services, middleware, or background scheduler logic.
"""
from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, ContextManager, Mapping, Protocol

logger = logging.getLogger(__name__)


class SpanInterface(Protocol):
    """Protocol defining required methods for a tracing span."""

    def set_attribute(self, key: str, value: Any) -> None:
        ...

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        ...

    def set_status(self, status: str, description: str | None = None) -> None:
        ...

    def record_exception(self, exception: Exception) -> None:
        ...


class TracerInterface(Protocol):
    """Protocol defining required methods for an OpenTelemetry-compatible tracer."""

    def start_span(
        self,
        name: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> ContextManager[SpanInterface]:
        ...


class NoOpSpan:
    """Zero-overhead default span implementation that performs no action."""

    def __init__(self, name: str, attributes: Mapping[str, Any] | None = None) -> None:
        self.name = name
        self.attributes = dict(attributes) if attributes else {}
        self.status = "UNSET"

    def __enter__(self) -> "NoOpSpan":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_val and isinstance(exc_val, Exception):
            self.record_exception(exc_val)
            self.set_status("ERROR", str(exc_val))

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        self.attributes.update(attributes)

    def set_status(self, status: str, description: str | None = None) -> None:
        self.status = status

    def record_exception(self, exception: Exception) -> None:
        self.attributes["exception.type"] = type(exception).__name__
        self.attributes["exception.message"] = str(exception)


class NoOpTracer:
    """Zero-overhead default tracer implementation."""

    def start_span(
        self,
        name: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> ContextManager[SpanInterface]:
        return NoOpSpan(name, attributes)


_global_tracer: TracerInterface = NoOpTracer()


def get_tracer() -> TracerInterface:
    """Retrieve the active OpenTelemetry-compatible tracer interface."""
    return _global_tracer


def set_tracer(tracer: TracerInterface) -> None:
    """Register a custom OpenTelemetry tracer implementation."""
    global _global_tracer
    _global_tracer = tracer
