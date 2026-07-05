# Environment Variables Reference

This table describes all environment variables supported by `realitytunnel-billing-server`.
Variables marked as **Required (Prod)** must be explicitly defined in staging and production environments.

| Variable Name | Default Value | Category | Required (Prod) | Description |
|---|---|---|---|---|
| `APP_VERSION` | `1.0.0` | App | No | Semantic version reported in `/health` and telemetry. |
| `ENVIRONMENT` | `development` | App | Yes | Operating mode: `development`, `testing`, `staging`, `production`. |
| `DEBUG` | `false` | App | Yes | Must be `false` in production. Enabling echoes SQL queries and detailed traces. |
| `LOG_LEVEL` | `INFO` | App | No | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `PORT` | `8080` | Server | No | Port bind for Uvicorn ASGI server. |
| `HOST` | `0.0.0.0` | Server | No | Host bind interface for ASGI server. |
| `POSTGRES_HOST` | `localhost` | Database | Yes | PostgreSQL server hostname or IP. |
| `POSTGRES_PORT` | `5432` | Database | No | PostgreSQL server port. |
| `POSTGRES_DB` | `billing` | Database | Yes | Database name. |
| `POSTGRES_USER` | `billing` | Database | Yes | Database authentication username. |
| `POSTGRES_PASSWORD`| — | Database | **YES** | Database password. Redacted from logs and traces. |
| `DATABASE_URL` | — | Database | No | Full SQLAlchemy DSN. Overrides individual database variables if provided. |
| `SECRET_KEY` | `dev-only...` | Security | **YES** | Cryptographic secret used for session hashing and security tokens. |
| `JWT_SECRET` | — | Security | **YES** | 32+ byte secret key used to sign Ed25519/HMAC authentication JWTs. |
| `MASTER_TOKEN_HASH`| — | Security | No | SHA-256 hash of admin master token for automated provisioning. |
| `API_KEY` | — | Security | No | Optional API key for system-to-system webhook and internal routes. |
| `GIT_COMMIT` | `unknown` | Metadata | No | Git SHA injected during Docker build for version tracking. |
| `BUILD_DATE` | `unknown` | Metadata | No | ISO timestamp injected during build for audit logging. |
| `DOCKER_IMAGE` | `billing...` | Metadata | No | Fully qualified Docker image tag displayed in health checks. |
