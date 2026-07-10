# RealityTunnel Architecture Guide

This document describes the canonical architecture for the RealityTunnel Backend and Infrastructure. It covers the physical deployment topology, core data flows, and trust boundaries.

## 1. System Topology

The system is distributed across two separate Virtual Private Servers (VPS) connected securely via WireGuard.

### High-Level Architecture

```mermaid
flowchart TD
    %% Define Styles
    classDef cloudflare fill:#f38020,stroke:#fff,stroke-width:2px,color:#fff
    classDef oracle fill:#f80000,stroke:#fff,stroke-width:2px,color:#fff
    classDef contabo fill:#003366,stroke:#fff,stroke-width:2px,color:#fff
    classDef internal fill:#2c3e50,stroke:#fff,stroke-width:1px,color:#fff

    User((User/Client))

    subgraph Internet
        CF["Cloudflare (DNS & WAF)"]:::cloudflare
    end

    subgraph Oracle ["Oracle Cloud (144.24.153.180) - Billing & Auth"]
        Caddy["Caddy (Reverse Proxy)"]:::internal
        API["Billing API (FastAPI)"]:::internal
        DB[(PostgreSQL)]:::internal
        Cache[(Redis)]:::internal
        
        Caddy <-->|HTTP:8080| API
        API <-->|TCP:5432| DB
        API <-->|TCP:6379| Cache
    end

    subgraph Contabo ["Contabo VPS (217.216.79.209) - VPN Core"]
        Marzban["Marzban Core"]:::internal
        Xray["Xray Engine (REALITY)"]:::internal
        
        Marzban <-->|gRPC/API| Xray
    end

    User -->|HTTPS| CF
    CF -->|HTTPS| Caddy
    
    User <==>|VLESS over REALITY| Xray
    
    %% WireGuard Connection
    API <==>|WireGuard (10.100.0.x)| Marzban
```

```text
Internet
      │
 ┌────────────┐
 │ Cloudflare │
 └─────┬──────┘
       │
       │
Oracle
144.24.153.180
──────────────────────────
Caddy
Billing API
Postgres
Redis

        ▲
        │ WireGuard
        ▼

Contabo
217.216.79.209
──────────────────────────
Marzban
Xray
REALITY
```

### Component Roles
- **Oracle (144.24.153.180):** The central brain. Handles all authentication, subscription logic, state management, and user data. It does not handle actual VPN traffic.
- **Contabo (217.216.79.209):** The edge node. Runs Marzban and Xray to terminate client VPN connections using VLESS/REALITY. Exclusively handles raw encrypted traffic.
- **WireGuard (10.100.0.1 <-> 10.100.0.2):** An encrypted tunnel ensuring that Oracle can securely orchestrate Contabo (via Marzban's API) without exposing Marzban to the public internet.

---

## 2. Trust Relationships

The system employs a strict zero-trust boundary between the control plane (Oracle) and the data plane (Contabo).

1. **Client -> Oracle:** Unsecured public access is proxied via Cloudflare to Caddy. Caddy terminates TLS and forwards to the API. All endpoints are protected by rate-limiting (Redis).
2. **Oracle -> Contabo:** The Billing API trusts Marzban via a long-lived JWT (`MARZBAN_API_TOKEN`). This connection is physically secured by WireGuard. Marzban binds its API exclusively to the `10.100.0.2` interface, making it unreachable from the public web.
3. **Internal Oracle (Docker):** Postgres and Redis are completely firewalled from the host. They are only accessible by the `billing-api` container over a private Docker network (`internal_net`).

---

## 3. Core Flows

### A. JWT Authentication Flow
1. User provides credentials (email/password or OAuth) to the `/auth/token` endpoint.
2. Oracle validates credentials against Postgres.
3. Oracle signs an Ed25519 JWT (access token) and returns it.
4. The client attaches this token in the `Authorization: Bearer` header for all subsequent API calls.
5. The API verifies the Ed25519 signature entirely statelessly (no DB lookup required for validation, though Redis checks for blacklisted tokens).

### B. Billing Flow (Subscription Purchase)
1. User requests a subscription checkout via the API.
2. API generates a payment intent using the active payment provider (e.g., Razorpay/LemonSqueezy) and returns the checkout URL.
3. Client completes the payment.
4. Payment gateway fires an asynchronous webhook to the `/webhooks/` endpoint.
5. API verifies the webhook HMAC signature.
6. API updates the user's subscription state in Postgres (e.g., `active`, sets `expires_at`).
7. **Triggers Provisioning Flow.**

### C. Provisioning Flow
1. A user's subscription becomes active (or is manually synced).
2. The `lifecycle_job_service` constructs the VLESS proxy configuration (UUID, Flow, Limit).
3. Oracle makes an HTTP POST request to `10.100.0.2:8000/api/user` (Contabo) over WireGuard, using the `MARZBAN_API_TOKEN`.
4. Marzban writes the configuration into Xray and hot-reloads.
5. Oracle saves the `subscription_url` and user connection parameters in Postgres.

### D. VPN Login Flow (Client Connection)
1. Client fetches their personal subscription link from Oracle (`/api/v1/users/me/subscription`).
2. Client parses the VLESS link.
3. Client opens a direct TCP connection to the Contabo IP (`217.216.79.209`).
4. Xray (via XTLS-Reality) authenticates the client's UUID and SNI. If successful, traffic is routed. If it fails, traffic is seamlessly proxied to the fallback SNI domain (stealth).

---

## 4. Failure Scenarios & Resilience

1. **Postgres Crash (Oracle):**
   - API endpoints requiring DB access fail gracefully (503 Service Unavailable).
   - VPN traffic (Contabo) is **100% unaffected**. Existing users remain connected.
   - Upon Postgres recovery, the API auto-reconnects.

2. **Redis Crash (Oracle):**
   - Rate limiting fails open or blocks requests (configurable).
   - API auto-reconnects via Docker container restarts.

3. **WireGuard Partition (Network Loss):**
   - Oracle cannot provision new users or sync data limits to Contabo.
   - The `failed_provision_retry` background worker detects the timeout and queues the user updates.
   - Existing VPN users on Contabo are **unaffected**.
   - Upon network restoration, the background worker flushes the queue to Marzban.

4. **Contabo Reboot/Crash:**
   - VPN connections drop.
   - Docker `restart: unless-stopped` brings Xray and Marzban back online.
   - Clients automatically reconnect (built into V2ray core behaviors).

5. **Oracle Reboot/Crash:**
   - API goes down. Users cannot sign up or buy subscriptions.
   - VPN traffic (Contabo) is **100% unaffected**. 
   - When Oracle comes back, `docker-compose` restores the API, DB, and Caddy.
