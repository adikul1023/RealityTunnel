"""
RealityTunnel Billing/Auth Server
Phase 1.1 — Foundation
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, verify_db
from app.routers import health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup / shutdown lifecycle."""
    logger.info("Billing server starting up…")
    logger.info("Database URL: %s", settings.database_url_safe)
    yield
    logger.info("Billing server shutting down…")
    await engine.dispose()


app = FastAPI(
    title="RealityTunnel Billing/Auth API",
    description="Billing & authentication backend for RealityTunnel VPN.",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health.router)


@app.get("/", summary="Root", tags=["Meta"])
async def root():
    return {
        "service": "RealityTunnel Billing/Auth API",
        "version": settings.app_version,
        "phase": "1.1 — Foundation",
        "docs": "/docs",
    }


@app.get("/version", summary="Version info", tags=["Meta"])
async def version():
    return {
        "version": settings.app_version,
        "environment": settings.environment,
    }
