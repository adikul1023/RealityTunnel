"""
Logging configuration for the billing server.

Call configure_logging() once at startup (from main or Uvicorn config).
Uses structlog-compatible formatting in production, simple format in dev.
Integrates RedactingFormatter (Phase 3.1.6) to ensure zero secrets leak in log output.
"""
import logging
import sys

from app.config import settings
from app.core.redaction import RedactingFormatter


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    fmt = (
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        if settings.environment == "development"
        else "%(asctime)s [%(levelname)s] %(name)s pid=%(process)d: %(message)s"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(RedactingFormatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))

    # Remove existing root handlers to prevent duplicated logs if configured multiple times
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Quiet noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.debug else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
