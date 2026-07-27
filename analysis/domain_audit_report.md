# Domain Audit: `stealthy.co.in`

This document lists every occurrence of the domain `stealthy.co.in` (and its subdomains) across the local codebase and remote servers. This information can be used to plan the domain migration.

## 1. Local Codebase (Windows)

### Client App (`src/`)
**✅ CLEAN:** 0 occurrences found! As designed, the C# client pulls domains dynamically at runtime.

### Frontend (Next.js)
* **`frontend-build/lib/config.ts`**
  * Line 9, 11: `api.stealthy.co.in`
  * Line 15, 17: `stealthy.co.in` (main site)
  * Line 21, 23: `downloads.stealthy.co.in`
  * Line 28: `support@stealthy.co.in`
  * Line 33: `status.stealthy.co.in`
* **`frontend-build/lib/api.ts`**
  * Line 5, 12: Comments mentioning `api.stealthy.co.in` and `edge.stealthy.co.in`

### Tests (C#)
* **`tests/OverREALITY.Tests/Infrastructure/DomainResolverTests.cs`**
  * Line 28, 33: `custom.api.stealthy.co.in`
* **`tests/OverREALITY.Tests/Core/ServerProfileValidatorTests.cs`**
  * Line 21, 53: `api.stealthy.co.in`
* **`tests/OverREALITY.Tests/Configuration/ConfigurationBuilderTests.cs`**
  * Line 16: `node1.stealthy.co.in`

### Documentation & Logs
* **`PROJECT_STATE.md`** & **`README.md`**
  * Mentions of `api` and `edge` endpoints.
* **`analysis/*`** & **`scratch/*`**
  * Multiple testing scripts and agent logs.

---

## 2. Server 1: Oracle Cloud (Billing API & Auth)
**Location:** `/opt/realitytunnel/releases/oracle-update-2026-07-10`

* **`app/config.py`**
  * Line 104: `vpn_edge_host: str = "edge.stealthy.co.in"`
* **`Caddyfile.prod`**
  * Line 10: `api.stealthy.co.in {`
* **`scripts/verify-production.sh`**
  * Lines 29, 30, 34, 37, 40, 44: Health checks hitting `api.stealthy.co.in`

*(Note: `.env` was checked with root permissions and no hardcoded domains were found there).*

---

## 3. Server 2: Contabo (VPN Edge & Marzban)
**Location:** `/opt/realitytunnel`

* **`scripts/verify-production.sh`**
  * Same health check script as Server 1.

*(Note: Xray/sing-box routing rules in the Marzban config may contain `api.stealthy.co.in` as part of the REALITY fallback rules, but this wasn't found in raw text files).*
