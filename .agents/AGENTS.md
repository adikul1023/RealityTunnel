# RealityTunnel Project Rules

## Phase Completion Rule

Every phase must end with:
1. A **green health check** — the service must respond with HTTP 200 to `GET /health` before the phase is declared complete.
2. A **Git commit** — all phase changes must be committed and pushed to `origin/main`.

These two conditions are mandatory before moving to the next phase.
