# Project State: Stealthy (RealityTunnel)

## Servers and Infrastructure
- **Server 1 (Billing API & Auth) - Oracle Cloud**
  - **IP:** 144.24.153.180
  - **User:** ubuntu
  - **Key:** `d:\My projects\VPN\AWSKEY\ssh-key-2026-03-01.key`
  - **Services:** Billing API (`ghcr.io/adikul1023/realitytunnel`), PostgreSQL (16-alpine), Redis (7-alpine), Caddy (2-alpine).
  - **Location:** `/opt/realitytunnel/releases/oracle-update-2026-07-10`
  - **Endpoint:** `api.stealthy.co.in`

- **Server 2 (VPN Edge & Marzban) - Contabo**
  - **IP:** 217.216.79.209
  - **User:** ak (sudo: TempPass)
  - **Key:** `~/.ssh/id_ed25519`
  - **Services:** Marzban (`gozargah/marzban:v0.8.3`), sing-box/Xray.
  - **Location:** `/opt/realitytunnel/current` (configs in `/opt/realitytunnel/marzban`)
  - **Endpoint:** `edge.stealthy.co.in`

## Current Deployment Status
- Production endpoints are live. No staging or development API exists.
- The Billing API acts as the sole source of truth and provisioning syncs UUIDs to PostgreSQL.
- Windows client does not connect to `.env` for VPN values. It retrieves them from `GET /api/client/config`.

## Database Schema & Migrations
- **Current DB:** PostgreSQL (db: `billing`)
- **Alembic Migration Status:** `a1b2c3d4e5f0 (head)`

## Architecture Change Notes
Before Phase 10.3C:
- **Remove Device** -> `is_active = false` (soft deactivate)

After Phase 10.3C:
- **Remove Device** -> `DELETE row` (hard delete) + token revocation (`DEVICE_REMOVED`)
- **Suspend Device** -> `is_active = false` (admin/suspension only)
- **Reactivate Device** -> `is_active = true`

## Active Phases
- **Current Phase:** End-to-end VPN connection.
- **Completed:** Production login, JWT, Refresh, 2FA, Secure credential storage, UI modernization, Single-instance application, Backend-driven VPN configuration, Removal of local `.env` dependency, Hard-delete device removal & legacy inactive device migration (`a1b2c3d4e5f0`).

## Known Bugs
- *To be discovered/documented*

## Completed Fixes
- UI modernization (first iteration)
- Single-instance application constraints
- Removal of `.env` dependency for VPN configuration
- Device lifecycle architectural split (Remove = Hard Delete vs Suspend = Soft Deactivate)

## Pending Work
- End-to-end VPN connection for the Windows Client.
- Android Client (Future Phase 3).

