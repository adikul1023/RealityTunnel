# v1.0.0 Known-Good Baseline — RealityTunnel

**Git tag:** `v1.0.0-working-vpn`
**Date:** 2026-07-14
**Status:** ✅ Verified end-to-end — VPN connects and routes all traffic through Contabo

## What Was Verified

- `GET https://api.stealthy.co.in/health` → HTTP 200
- `Fetching HTTP api.ipify.org` through tunnel → returns `217.216.79.209` (Contabo IP)
- `sing-box` TUN interface fully routed all OS traffic through the VLESS+REALITY tunnel

## Component Versions

| Component | Version |
|-----------|---------|
| sing-box (Windows client) | 1.13.0 (Revision `6da7e53`) |
| Marzban | `gozargah/marzban:v0.8.3` |
| Xray (inside Marzban) | `24.12.31` |
| RealityTunnel API image | `ghcr.io/adikul1023/realitytunnel:sha-5b8bf0b5df07...` |

## Files in This Directory

| File | Description |
|------|-------------|
| `xray_config.json` | Live Contabo Xray configuration at time of baseline |
| `config.json` | Generated Windows client sing-box config at time of baseline |
| `singbox.log` | Successful session log showing connection to Contabo |
| `oracle.env` | Oracle billing server `.env` structure (secrets redacted) |
| `versions.txt` | Component versions (machine-readable copy) |

> **Note:** `vpn_profile.dat` is stored encrypted via Windows DPAPI in
> `%LOCALAPPDATA%\OverREALITY\Secure\` and cannot be archived in plaintext.
> It is recreated automatically when the user logs in.

## Known Configuration That Must Match

If any of these drift, the VPN will connect but silently drop all traffic:

```
SNI:      dl.google.com
short_id: ""  (empty string)
port:     443
dest:     dl.google.com:443
flow:     ""  (empty — Marzban injects per-user dynamically)
```

## Regression Test

```bash
python tests/regression/verify_config_sync.py
```

This script verifies the live Contabo Xray config against these baseline values via SSH.
