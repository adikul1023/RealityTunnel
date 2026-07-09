# Marzban Downstream Modifications

This directory contains the Dockerfile and patches to build a slightly modified image of Marzban.

## `marzban-host.patch`

**Upstream Version:** `gozargah/marzban:latest` (as of 2026)  
**Purpose:** Upstream Marzban hardcodes `bind_args['host'] = '127.0.0.1'` in `main.py` when TLS certificates are missing, overriding the `UVICORN_HOST` environment variable. This patch allows Marzban to bind to `0.0.0.0` securely within its own internal Docker network namespace, avoiding the need to run `network_mode: service:caddy` or rely on complex sidecars.  
**Removal Criteria:** If upstream Marzban merges support for respecting `UVICORN_HOST` natively when running behind an internal reverse proxy without TLS (or officially documents how to bypass the restriction), this patch and downstream image can be safely deleted.
