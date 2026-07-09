# Security Policies & Threat Model (RealityTunnel)

## 1. Threat Model & Trust Boundaries
The RealityTunnel Billing Backend operates as a highly privileged orchestrator within the VPN infrastructure. 
- **Trust Boundary:** The Caddy Reverse Proxy serves as the absolute perimeter. No traffic reaches the Billing API, PostgreSQL, or Redis without passing through Caddy. 
- **Untrusted Entities:** End users, external payment gateways (Razorpay webhooks), and potentially compromised Marzban nodes.
- **Trusted Entities:** The PostgreSQL database, Redis (rate-limiting backend), and internal cron schedulers.

## 2. Security Assumptions
- **Network Isolation:** Internal services (`postgres`, `redis`, `billing-api`) do not bind ports to the host interface (`0.0.0.0`). They exist solely on the `internal_net` / `ingress_net` Docker bridges.
- **Secret Supremacy:** System integrity relies entirely on cryptographic secrets (Ed25519 signing keys, JWT secrets, database passwords). These must never be hardcoded or checked into version control.

## 3. Secret Management & Key Rotation
The system uses asymmetric Ed25519 cryptography to issue JWTs. 
### Rotation Procedure:
1. Generate a new Ed25519 private/public key pair (e.g., using `openssl` or the internal generator).
2. Replace the `.pem` files in the production secret volume.
3. Restart the `billing-api` containers.
4. **Impact:** All existing sessions will immediately terminate (HTTP 401). Users must log in again to mint new tokens.

## 4. Payment Reconciliation Design
Webhooks from payment providers (e.g., Razorpay) are inherently untrusted and subject to out-of-order delivery, duplication, or spoofing (if signature validation fails).
- Webhooks trigger a state transition, but do NOT directly provision VPN access.
- A background `LifecycleJobService` scheduler asynchronously polls pending payments and securely provisions access.
- Both the Webhook and the Scheduler use `SELECT FOR UPDATE SKIP LOCKED` database locks to prevent race conditions or double-provisioning.

## 5. Supported Deployment Architecture
The backend must be deployed using Docker Compose on a hardened Linux host.
- Python runtime runs as a non-root `billing` user.
- Filesystem is restricted (`/app` is owned by `billing`, but configuration files should be read-only at runtime).
- Dependencies are isolated inside the container image, minimizing supply-chain drift.

## 6. Incident Response & Backup Recovery
In the event of database corruption, catastrophic failure, or total state loss:
1. Identify and halt the compromised service.
2. Restore PostgreSQL from the latest `.dump` or `.sql` backup.
3. Restart the `billing-api`. The system is designed to self-heal: the `LifecycleJobService` will automatically resume polling stale pending payments and resync with Marzban.

## 7. Accepted Risks
- **Dependency Lag:** Without a strict lockfile (e.g., `uv.lock` or `Pipfile.lock`), identical builds could hypothetically fetch newer, vulnerable transitive dependencies. Mitigation: A lockfile migration is planned.
- **Provider API Outages:** If the payment provider's API goes down, the reconciliation scheduler will retry with exponential backoff until the timeout window expires. Users may experience delayed provisioning during upstream outages.

## 8. Software Bill of Materials (SBOM)
To facilitate future CVE scanning and compliance, an SBOM is generated using `syft`.
- **Command:** `syft scan . -o spdx-json=sbom.spdx.json`
- The `sbom.spdx.json` file is stored in the repository root and should be updated whenever `requirements.txt` changes.
