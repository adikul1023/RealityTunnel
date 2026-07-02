# Phase 0.3 — Marzban Runtime Validation

Empirical test suite for RealityTunnel's Marzban integration.
All tests produce objective measurements, not assumptions.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.8+ on host | Only stdlib used — no pip install |
| Marzban running in Docker | `cd compose && docker compose up -d` |
| Admin password | `labtest123` (set in common.py `ADMIN_PASS`) |
| Docker Desktop (Windows) | host.docker.internal must be reachable from container |

---

## Running

```powershell
cd "D:\My projects\VPN\OverREALITY\RealityTunnel-Lab\tests\phase03"

# All automatable tests
python run_all.py

# Skip the docker down/up in test_08
python run_all.py --skip-restart

# Skip the live webhook container-restart in test_10
python run_all.py --skip-webhook

# Run specific tests only
python run_all.py --only 7 9 10

# Run a single test directly
python test_07_core_restart.py
```

Results are appended to `results/run.log` after each run.

---

## Test Map

| # | File | Automated | Notes |
|---|---|---|---|
| 01 | test_01_disable_user.py | Server side ✓ | Tunnel measurement: CLIENT REQUIRED |
| 02 | test_02_enable_user.py | Server side ✓ | Tunnel measurement: CLIENT REQUIRED |
| 03 | test_03_uuid_change.py | Server side ✓ | Session behavior: CLIENT REQUIRED |
| 04 | test_04_expiry.py | ✓ Full | Measures natural expiry lag via background job |
| 05 | test_05_quota.py | ✓ Full | Injects fake traffic via SQLite; measures enforcement lag |
| 06 | test_06_revoke_sub.py | Server side ✓ | Session behavior: CLIENT REQUIRED |
| 07 | test_07_core_restart.py | ✓ Full | POST /api/core/restart — measures downtime |
| 08 | test_08_persistence.py | ✓ Full | docker compose down/up — verifies all state persists |
| 09 | test_09_admin_token.py | ✓ Full | JWT decode, all failure modes, no refresh endpoint |
| 10 | test_10_webhooks.py | ✓ Full* | *Restarts container twice. Set SKIP_WEBHOOK_LIVE=1 to skip live capture |

---

## CLIENT REQUIRED — Active Session Tests (01–03, 06)

Tests 01–03 and 06 fully verify the **server side** (API, Marzban logs, Xray state).
The tunnel-layer measurements below require a VPN client connected to the VLESS TCP REALITY inbound.

### What to do

1. Create the test user using the relevant test or manually via the API.
2. Import the subscription link into **sing-box** or **Nekoray**.
3. Connect and establish an active tunnel.
4. Run the test script — it will call the API at the right moment.
5. Observe the client side as instructed in the `CLIENT REQUIRED` output.

### What to measure

| Scenario | Metric |
|---|---|
| Disable while connected | Time from `PUT status=disabled` to first ping loss |
| Re-enable | Time from `PUT status=active` to first successful new connection |
| UUID rotation | Whether existing session drops; whether old config is rejected on reconnect |
| Expiry | Same as disable — but triggered by background job, not API call |

### Predicted behavior (source-code proven, not yet empirically measured)

- **RemoveUser does NOT kill existing sessions.** Xray source: `RemoveUser` deletes from two `sync.Map`s only. Active goroutines are fire-and-forget — no cancellation signal.
- **Authentication is checked once per TCP connection.** After auth, the validator is never queried again for that connection.
- **Tunnel survives until:** TCP keepalive failure, client disconnect, or `ConnectionIdle` Xray policy fires (not configured in lab — default Linux keepalive is ~2 hours).
- **New connections:** rejected immediately after `RemoveUser`.
- **Reconnect after re-enable:** works immediately — `update_user` (RemoveUser + AddUser) restores the UUID in Xray's handler.

---

## Architecture Notes

### Background jobs (from Marzban source)

| Job | Interval | What it does |
|---|---|---|
| `review()` | **10 s** | `active → limited` if `used_traffic >= data_limit`; `active → expired` if `expire <= now` |
| `record_user_usages()` | **10 s** | Polls Xray stats API, updates `used_traffic` in DB |
| `core_health_check()` | **10 s** | Restarts Xray if it has exited |
| `send_notifications()` | **30 s** | Drains webhook notification queue |
| `remove_expired_users()` | **6 h** | Auto-deletes users with `auto_delete_in_days` set |

### Webhook system

- Requires `WEBHOOK_ADDRESS` in `.env` (startup-only — needs container restart to change).
- Auth: `x-webhook-secret` header (plain string, no HMAC).
- **No timeout on HTTP calls** — your webhook endpoint must respond quickly or Marzban blocks.
- Retry: 3 attempts × 180 s delay.
- Login events are **not** sent via webhook.

### Admin token

- Expiry: **86400 s (24 hours)**.
- No refresh endpoint — re-authentication is the only renewal mechanism.
- Algorithm: HS256.
- The Billing server must re-authenticate before the token expires.

---

## File Structure

```
tests/phase03/
├── README.md               this file
├── common.py               shared client, helpers, Docker utilities
├── run_all.py              orchestrator
├── test_01_disable_user.py
├── test_02_enable_user.py
├── test_03_uuid_change.py
├── test_04_expiry.py       natural expiry timing (fully automated)
├── test_05_quota.py        quota enforcement via SQLite injection (fully automated)
├── test_06_revoke_sub.py
├── test_07_core_restart.py
├── test_08_persistence.py  docker down/up cycle
├── test_09_admin_token.py
├── test_10_webhooks.py     live webhook capture (restarts container)
└── results/
    └── run.log             cumulative test results
```
