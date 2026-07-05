# System Architecture & Component Interactions

The RealityTunnel billing and authentication server is built as an asynchronous, modular, high-performance backend designed for orthogonal separation of concerns.

## 1. High-Level Architecture Diagram

```
[ External Clients / VPN Nodes ] ---> [ Nginx / Cloudflare Ingress ]
                                              │
                                              ▼ (HTTPS / Port 8080)
                         ┌────────────────────────────────────────┐
                         │  RealityTunnel Billing Server (FastAPI)│
                         │                                        │
                         │  ┌──────────────────────────────────┐  │
                         │  │  Router Layer (/api/auth, /health)│  │
                         │  └─────────────────┬────────────────┘  │
                         │                    │                   │
                         │  ┌─────────────────▼────────────────┐  │
                         │  │  Service Layer (Business Logic)  │  │
                         │  └─────────────────┬────────────────┘  │
                         │                    │                   │
                         │  ┌─────────────────▼────────────────┐  │
                         │  │ Repository Layer (SQLAlchemy 2.0)│  │
                         │  └─────────────────┬────────────────┘  │
                         └────────────────────┼───────────────────┘
                                              │ (asyncpg / 5432)
                                              ▼
                         ┌────────────────────────────────────────┐
                         │  PostgreSQL 16+ Production Database    │
                         └────────────────────────────────────────┘
```

## 2. Orthogonal Subsystems

To guarantee stability, security, and maintainability, auxiliary production subsystems are isolated from business logic:

### Security Hardening (`app/security/` & `app/security_hardening/`)
- Handles Ed25519 cryptographic token signing, refresh token rotation with replay detection, rate limiting, and zero-secret logging redaction.
- Operates via ASGI middleware and FastAPI dependency injection without altering router business implementations.

### Disaster Recovery & Backups (`app/recovery/`)
- Manages pre-flight snapshots, SHA-256 integrity checks, and point-in-time database restoration.
- Can be invoked independently via CLI scripts or automated pre-deployment pipelines.

### Observability & Telemetry (`app/observability/`)
- Exports Prometheus gauges and counters (`/api/metrics`), structured JSON logging, and correlation IDs across distributed tracing boundaries.

### Performance & Caching (`app/performance/`)
- Implements connection pool tuning, N+1 query optimization, and in-memory plan caching following the Zero-Secret Caching Rule.
