# Marzban Lab Notes

## Goal

Validate the official Marzban Docker deployment locally without modifying Marzban source, and prove that the admin panel remains accessible after a container restart.

## What Was Changed In The Lab Wrapper

- Copied the official Marzban `docker-compose.yml` into `RealityTunnel-Lab/compose/docker-compose.yml`.
- Kept only the minimum lab-only changes required for Docker Desktop:
	- published port `8000` so the panel is reachable from Windows
	- workspace bind mount for persistence at `RealityTunnel-Lab/data/marzban`
	- local self-signed TLS files mounted from `RealityTunnel-Lab/configs/certs`
	- lab-only environment variables in `RealityTunnel-Lab/compose/.env` for HTTPS binding and persistent storage paths

No Marzban source files were modified.

## Verified Runtime State

- Admin panel is reachable at `https://localhost:8000/dashboard/`.
- Dashboard returns `200 OK`.
- A sudo admin named `admin` exists and survives a full `docker compose down` / `docker compose up -d` cycle.

## Running Containers

- Container name: `compose-marzban-1`
- Image: `gozargah/marzban:latest`

## Mounted Volumes

Observed with `docker inspect`:

- `RealityTunnel-Lab/data/marzban` -> `/var/lib/marzban`
- `RealityTunnel-Lab/configs/certs` -> `/certs`

There are no anonymous Docker volumes holding Marzban state. The only stateful path in the lab is the workspace bind mount.

## Network Mode

- Lab compose uses normal bridge networking with a published port.
- Published port: `8000:8000`

## Database Location

- In-container path: `/var/lib/marzban/db.sqlite3`
- Workspace path: `RealityTunnel-Lab/data/marzban/db.sqlite3`
- Database type: SQLite

## Xray Configuration Location

- In-container path: `/var/lib/marzban/xray_config.json`
- Workspace path: `RealityTunnel-Lab/data/marzban/xray_config.json`

Observed related file:

- Legacy stock file inside the image: `/code/xray_config.json`

## Log Locations

Operational logging is available through container logs:

- `docker compose logs -f marzban`
- `docker logs compose-marzban-1`

Inside the container, Marzban exposes runtime config/state files under `/var/lib/marzban` and the application startup logs are emitted to the container stdout/stderr stream.

## Backups

For this lab, back up the following workspace paths:

1. `RealityTunnel-Lab/data/marzban`
2. `RealityTunnel-Lab/compose/.env`
3. `RealityTunnel-Lab/compose/docker-compose.yml`
4. `RealityTunnel-Lab/configs/certs`

If you rebuild the lab from scratch, the only required persistent state is `RealityTunnel-Lab/data/marzban`.

Recommended backup method:

- Stop the stack with `docker compose down`.
- Copy the entire `RealityTunnel-Lab/data/marzban` directory.
- Also copy the lab `.env` and compose file so the TLS and persistence settings can be restored exactly.
- If you want a full restore path, keep the cert/key pair in `RealityTunnel-Lab/configs/certs`.

## Useful Commands

```powershell
cd "d:\My projects\VPN\OverREALITY\RealityTunnel-Lab\compose"
docker compose up -d
docker compose down
docker compose logs --no-color --tail 20 marzban
docker compose exec -T marzban marzban-cli admin list -u admin
```

## Notes

- The panel is served over HTTPS because the lab uses a local self-signed certificate.
- The admin account was created with the official CLI inside the running container.
- Persistence was verified by restarting the stack and confirming that the `admin` row remained present.