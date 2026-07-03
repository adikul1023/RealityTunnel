# Phase 1.4 Roadmap — Device Management & Admin Architecture Refinement

**Status:** Planned / Approved Specification
**Target Phase:** Phase 1.4 (Post-Authentication Freeze)
**Date Refined:** 2026-07-03

---

## Overview

With the Authentication subsystem (Phase 1.3) audited and frozen, Phase 1.4 introduces **Device Management**, **Abstract Subscription Plan Enforcement**, **Signal Collection**, and **Administrative Security Architecture**. 

To maintain clean architecture and avoid premature optimization or coupling, Phase 1.4 strictly separates device binding from authentication logic and defers advanced fraud-detection capabilities to future phases.

---

## Detailed Specification

### Phase 1.4.1 — Device Registration Domain Service

#### Responsibilities
- Manage the lifecycle of client installations identified by `device_guid`.
- Bind a `device_guid` to an `account_id` upon initial authentication or explicit registration.
- Maintain device metadata: `first_seen_at`, `last_seen_at`, `is_active`, and friendly device names (e.g., "Arun's Windows Desktop").
- Enforce ownership validation: prevent a `device_guid` currently actively bound to Account A from being hijacked by Account B without explicit revocation or transfer authorization.

#### Architectural Constraints
- Pure domain service (`DeviceService`), completely independent of FastAPI routers, HTTP request/response DTOs, or JWT crypto generation.
- Repositories (`DeviceRepository`) handle all persistence and query execution with row-level locking where concurrent registration races could occur.

---

### Phase 1.4.2 — Device Management API Endpoints

#### Scope
Implement thin REST API orchestration endpoints under `/api/devices`:
- `GET /api/devices` — List all registered devices for the currently authenticated account.
- `PATCH /api/devices/{device_guid}` — Update metadata (e.g., friendly name, active toggle).
- `DELETE /api/devices/{device_guid}` — Revoke device access, delete device registration, and trigger cascade revocation of all associated refresh tokens for that specific device.

#### Security & DI
- Protected by `get_current_account()` dependency (requiring a valid Ed25519 Access JWT from Phase 1.3).
- Endpoints must verify that the target `device_guid` belongs to the authenticated `account_id` before performing updates or deletions (preventing Insecure Direct Object Reference / IDOR vulnerabilities).

---

### Phase 1.4.3 — Abstract Subscription Plan & Device Limits

#### Core Principle: No Hardcoded Plans
- Do **NOT** hardcode commercial tiers (`Free`, `Pro`, `Family`, `VIP`) into enum logic or `if/else` control structures.
- Introduce an abstract `SubscriptionPlan` domain entity (or data structure) representing plan capabilities:
  ```python
  @dataclass(frozen=True)
  class SubscriptionPlan:
      plan_id: str
      name: str
      max_devices: int
      max_concurrent_ips: int
      allow_offline_licensing: bool
  ```
- Phase 1.4 will implement device limit enforcement against `max_devices` defined by the account's assigned `SubscriptionPlan`.
- Phase 2 (Billing & Licensing expansion) will populate and expand these plans dynamically from database tables or payment provider integrations without altering the core device limit enforcement engine.

---

### Phase 1.4.4 — Baseline Signal Collection (No GeoIP/ASN Yet)

#### Scope of Collection
Limit data collection strictly to baseline network and session signals already available during authentication and VPN interaction:
- **Client IP address** (extracted from HTTP request socket / X-Forwarded-For trusted proxy headers).
- **Device GUID** (presented in login/refresh requests).
- **Timestamps** (`issued_at`, `last_seen_at`, `refresh_event_time`).
- **Session & Refresh Event counts** (frequency of token rotations per device/account).

#### Explicitly Deferred to Later Fraud-Detection Phase
To prevent scope creep and maintain high performance, the following complex analytical evaluations are **strictly excluded** from Phase 1.4:
- GeoIP location lookup and country/city resolution.
- Autonomous System Number (ASN) and ISP organization lookups.
- "Impossible Travel" velocity calculations (e.g., logging in from New York and London within 10 minutes).
- Residential vs. Datacenter / Proxy IP classification.
- Anomaly scoring engines or ML-based behavioral blocking.

*Reasoning:* These features require external databases (MaxMind/IP2Location), asynchronous enrichment pipelines, and complex heuristics that would delay core VPN device functionality. They will be integrated as an asynchronous event-driven fraud pipeline in a dedicated future phase.

---

### Phase 1.4.5 — Administrative Authentication & Security Architecture Design

#### Design Questions & Approved Recommendations

1. **Separate JWT or Share Client JWT?**
   - **Recommendation: Completely Separate Admin JWT.**
   - Admin access tokens must use a distinct token structure: different issuer (`"RealityTunnel Admin/Auth"`), different audience (`"RealityTunnel Admin Portal"`), different required claims (`admin_id`, `role`, `permissions`), and a shorter lifetime (e.g., 10–15 minutes).
   - Reusing client VPN JWTs or adding `is_admin=True` flags to client tokens creates catastrophic privilege escalation risks if a client signing key or token verification path is compromised.

2. **Separate Authentication Service?**
   - **Recommendation: Dedicated `AdminAuthenticationService`.**
   - Admin identities must NOT use Account IDs (`RT-XXXX`) or SHA-256 machine-generated Master Tokens.
   - Admin accounts must reside in a separate database table (`admin_users`) authenticated via email/username, strong human-chosen passwords hashed with **Argon2id** (per `ADR-002`), and mandatory multi-factor authentication (MFA).

3. **Network Isolation: VPN-only? WireGuard? mTLS? IP Allowlist?**
   - **Recommendation: Defense-in-Depth Layered Network Architecture.**
   - *Layer 1 (Transport Isolation):* Administrative API endpoints (`/api/admin/*`) must **NEVER** be publicly accessible over the public Caddy HTTPS ingress. They must bind exclusively to a private administrative interface accessible only via a dedicated **WireGuard management tunnel** or **Mutual TLS (mTLS)** client certificate authentication.
   - *Layer 2 (IP Allowlist):* Even within the private WireGuard/management subnet, enforce an IP allowlist restricting ingress to known operator IP ranges (e.g., `10.100.0.0/24`).
   - *Layer 3 (Application MFA):* Require Time-Based One-Time Password (TOTP / RFC 6238) or WebAuthn/FIDO2 verification during admin login before issuing an Admin JWT.

---

### Phase 1.4.6 — Administrative API Endpoints

- Implementation of `/api/admin/*` endpoints (user management, subscription overrides, device force-revocation, audit log inspection) is strictly blocked until Phase 1.4.5 security architecture is implemented and verified.
- Endpoints will consume the separate Admin JWT dependency (`get_current_admin_user()`).

---

### Phase 1.4.7 — White-Box Security Audit

- A comprehensive white-box security audit of the entire Device Management and Admin Authentication subsystem, following the exact methodology of Phase 1.3.7.
- Required before tagging Phase 1.4 complete or initiating Phase 2.
