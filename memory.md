# Stealthy / RealityTunnel Memory

## Core Principles
1. **Production-First**: Always assume production. No placeholder values, no hardcoded alternative environments. 
2. **Endpoints**: 
   - Billing API: `https://api.stealthy.co.in`
   - VPN Edge: `edge.stealthy.co.in`
   - No staging or dev endpoints exist. NEVER invent new ones.
3. **Architecture Rules**:
   - The Billing API is the single source of truth for licensing and config.
   - The Windows client must NEVER expose server IPs to the user.
   - Connections occur exclusively through the Billing API.
4. **Authentication Flow**:
   - Format: `AccountID:MasterToken`
   - Initial request: `POST /api/auth/login`
   - If 2FA required: client prompts for TOTP and resubmits to `POST /api/auth/login` with `two_fa_code`. (There is NO separate verify-2fa endpoint).
5. **VPN Configuration**:
   - Client calls `GET /api/client/config` (must have valid JWT, registered device, active sub).
   - Backend returns: `server_host`, `server_port`, `uuid`, `public_key`, `short_id`, `sni`, `preferred_dns`.
   - Client generates `sing-box` config dynamically.
   - Client resolves `edge.stealthy.co.in` to IP *only* for Windows routing; passes the domain to `sing-box`. Never hardcode IPs.

## Infrastructure Observations
- **Oracle (Billing API)**: Uses Docker Compose. Runs `ghcr.io/adikul1023/realitytunnel`, `postgres`, `redis`, `caddy`. Current deployment is under `/opt/realitytunnel/releases/oracle-update-2026-07-10`.
- **Contabo (Marzban/VPN Edge)**: Uses Docker Compose. Runs `gozargah/marzban:v0.8.3`. Current deployment is under `/opt/realitytunnel/current` with volumes in `/opt/realitytunnel/marzban`.

## Change Management (Mandatory)
Before modifying architecture, MUST:
1. Produce Root Cause Analysis.
2. Produce Implementation Plan.
3. Wait for approval.
4. Implement only approved scope.
5. Produce verification evidence.
