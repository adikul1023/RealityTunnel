"""
Logging configuration for the billing server.

Call configure_logging() once at startup (from main or Uvicorn config).
Uses structlog-compatible formatting in production, simple format in dev.
"""
import logging
import sys

from app.config import settings


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    fmt = (
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        if settings.environment == "development"
        else "%(asctime)s [%(levelname)s] %(name)s pid=%(process)d: %(message)s"
    )

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Quiet noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.debug else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
