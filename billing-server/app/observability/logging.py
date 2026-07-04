"""
app/observability/logging.py — Structured JSON Logging & Sampling (Phase 3.2.1 & 3.2.12).
Provides JSON log formatting with automatic correlation context injection and secret redaction,
along with configurable log sampling that guarantees error logs are never sampled out.
"""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.core.redaction import redact_string
from app.observability.context import (
    get_component,
    get_correlation_id,
    get_operation,
    get_request_id,
)


class LogSamplingFilter(logging.Filter):
    """
    Configurable log sampling filter (Phase 3.2.12).
    Allows sampling log volume (e.g. 1.0 = 100%, 0.1 = 10%, 0.01 = 1%).
    Guarantees that error logs (level >= ERROR) or exceptions are NEVER sampled.
    """

    def __init__(self, name: str = "", sampling_rate: float | None = None) -> None:
        super().__init__(name)
        self._rate = sampling_rate

    @property
    def rate(self) -> float:
        if self._rate is not None:
            return self._rate
        return getattr(settings, "log_sampling_rate", 1.0)

    def filter(self, record: logging.LogRecord) -> bool:
        # Errors and exceptions are never sampled
        if record.levelno >= logging.ERROR or record.exc_info is not None:
            return True
        if getattr(record, "force_sample", False):
            return True
        current_rate = self.rate
        if current_rate >= 1.0:
            return True
        if current_rate <= 0.0:
            return False
        return random.random() <= current_rate


class StructuredJsonFormatter(logging.Formatter):
    """
    Structured JSON log formatter (Phase 3.2.1).
    Emits single-line JSON records containing required observability attributes:
      timestamp, level, service, environment, request_id, correlation_id,
      component, operation, duration_ms, status, exception_type, message.
    Always runs output through secret redaction to prevent accidental credential leakage.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        # Format timestamp in UTC ISO-8601
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        timestamp_str = dt.isoformat()

        # Extract context or fallbacks
        req_id = getattr(record, "request_id", None) or get_request_id()
        corr_id = getattr(record, "correlation_id", None) or get_correlation_id() or req_id
        comp = getattr(record, "component", None) or get_component() or record.name
        op = getattr(record, "operation", None) or get_operation() or record.funcName

        duration = getattr(record, "duration_ms", None)
        if duration is not None:
            try:
                duration = round(float(duration), 2)
            except (ValueError, TypeError):
                duration = None

        status = getattr(record, "status", None)
        if status is None:
            status = "error" if record.levelno >= logging.ERROR else "ok"

        exc_type: str | None = None
        if record.exc_info and record.exc_info[0]:
            exc_type = record.exc_info[0].__name__
        elif getattr(record, "exception_type", None):
            exc_type = str(getattr(record, "exception_type"))

        message = record.getMessage()
        if record.exc_info and not exc_type:
            exc_type = "Exception"

        log_record = {
            "timestamp": timestamp_str,
            "level": record.levelname,
            "service": "RealityTunnel",
            "environment": getattr(settings, "environment", "development"),
            "request_id": req_id,
            "correlation_id": corr_id,
            "component": comp,
            "operation": op,
            "duration_ms": duration,
            "status": status,
            "exception_type": exc_type,
            "message": message,
        }

        # Format as JSON and apply mandatory zero-secret redaction
        raw_json = json.dumps(log_record, ensure_ascii=False)
        return redact_string(raw_json)
