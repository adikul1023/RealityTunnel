"""
app/observability/context.py — Async Correlation Context Management (Phase 3.2.2 & 3.2.3).
Uses contextvars to propagate request IDs and correlation IDs across chained domain operations,
background tasks, and log records without modifying function signatures.
"""
from __future__ import annotations

import contextvars
from typing import Any, Mapping

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
_correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")
_component_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("component", default="")
_operation_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("operation", default="")


def get_request_id() -> str:
    """Retrieve the current request ID."""
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> contextvars.Token[str]:
    """Set the current request ID."""
    return _request_id_ctx.set(request_id)


def get_correlation_id() -> str:
    """Retrieve the current correlation ID (falls back to request_id if unset)."""
    val = _correlation_id_ctx.get()
    return val if val else _request_id_ctx.get()


def set_correlation_id(correlation_id: str) -> contextvars.Token[str]:
    """Set the current correlation ID."""
    return _correlation_id_ctx.set(correlation_id)


def get_component() -> str:
    """Retrieve the current component name."""
    return _component_ctx.get()


def set_component(component: str) -> contextvars.Token[str]:
    """Set the current component name."""
    return _component_ctx.set(component)


def get_operation() -> str:
    """Retrieve the current operation name."""
    return _operation_ctx.get()


def set_operation(operation: str) -> contextvars.Token[str]:
    """Set the current operation name."""
    return _operation_ctx.set(operation)


def bind_context(
    request_id: str | None = None,
    correlation_id: str | None = None,
    component: str | None = None,
    operation: str | None = None,
) -> dict[str, contextvars.Token[str]]:
    """
    Bind multiple context variables simultaneously. Returns a mapping of contextvar tokens
    that can be used to reset values.
    """
    tokens: dict[str, contextvars.Token[str]] = {}
    if request_id is not None:
        tokens["request_id"] = _request_id_ctx.set(request_id)
        if correlation_id is None and not _correlation_id_ctx.get():
            tokens["correlation_id"] = _correlation_id_ctx.set(request_id)
    if correlation_id is not None:
        tokens["correlation_id"] = _correlation_id_ctx.set(correlation_id)
    if component is not None:
        tokens["component"] = _component_ctx.set(component)
    if operation is not None:
        tokens["operation"] = _operation_ctx.set(operation)
    return tokens


def reset_context(tokens: Mapping[str, contextvars.Token[str]]) -> None:
    """Reset context variables using previously acquired tokens."""
    if "request_id" in tokens:
        _request_id_ctx.reset(tokens["request_id"])
    if "correlation_id" in tokens:
        _correlation_id_ctx.reset(tokens["correlation_id"])
    if "component" in tokens:
        _component_ctx.reset(tokens["component"])
    if "operation" in tokens:
        _operation_ctx.reset(tokens["operation"])


def clear_context() -> None:
    """Clear all context variables back to default empty strings."""
    _request_id_ctx.set("")
    _correlation_id_ctx.set("")
    _component_ctx.set("")
    _operation_ctx.set("")
