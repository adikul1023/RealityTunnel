# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps for asyncpg (requires Cython)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Use BuildKit cache mount for pip optimization
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# OCI Image Labels
ARG BUILD_DATE="unknown"
ARG GIT_COMMIT="unknown"
ARG VERSION="1.0.0"

LABEL org.opencontainers.image.title="RealityTunnel Billing & Authentication Service" \
      org.opencontainers.image.description="High-performance VPN billing, subscription, and authentication backend" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/adikul1023/RealityTunnel" \
      org.opencontainers.image.vendor="OverREALITY" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install tini init system and libpq runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Non-root user for security and read-only filesystem preparation
RUN groupadd --gid 1001 billing \
    && useradd --uid 1001 --gid billing --shell /bin/bash --create-home billing \
    && mkdir -p /app/backups /app/brain /tmp \
    && chown -R billing:billing /app /tmp \
    && chmod 700 /app/backups /app/brain /tmp

COPY --chown=billing:billing . .

USER billing

# Expose HTTP port
EXPOSE 8080

# Native health check
HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
