"""
Logging configuration for the billing server (Phase 3.1 & 3.2).

Call configure_logging() once at startup (from main or Uvicorn config).
Uses StructuredJsonFormatter in production or when log_format="json", and simple RedactingFormatter in dev console.
Integrates LogSamplingFilter to support configurable sampling while ensuring errors are never sampled.
"""
from __future__ import annotations

import logging
import sys

from app.config import settings
from app.core.redaction import RedactingFormatter
from app.observability.logging import LogSamplingFilter, StructuredJsonFormatter


def configure_logging() -> None:
    level = getattr(logging, getattr(settings, "log_level", "INFO").upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    log_fmt_setting = getattr(settings, "log_format", "json").lower()
    env_setting = getattr(settings, "environment", "development").lower()

    if log_fmt_setting == "json" or env_setting in ("production", "staging"):
        handler.setFormatter(StructuredJsonFormatter())
    else:
        fmt = (
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            if env_setting == "development"
            else "%(asctime)s [%(levelname)s] %(name)s pid=%(process)d: %(message)s"
        )
        handler.setFormatter(RedactingFormatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))

    # Remove existing root handlers to prevent duplicated logs if configured multiple times
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Add sampling filter
    sampling_filter = LogSamplingFilter()
    handler.addFilter(sampling_filter)

    # Quiet noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if getattr(settings, "debug", False) else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
