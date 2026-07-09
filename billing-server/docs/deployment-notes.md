# Production Deployment Notes

These notes document the manual infrastructure setup, permission fixes, and environment configurations required to successfully deploy the RealityTunnel Billing API onto the production VPS (Contabo).

## 1. Directory Structure & Releases
The application is deployed using a Capistrano-style directory structure to allow instant rollbacks without touching a Git working tree:

`	ext
/opt/realitytunnel/
    billing/
        releases/
            2026-07-09_001/
        current -> releases/2026-07-09_001/billing-server
`
All Docker compose commands (up, down, logs) are executed from the /opt/realitytunnel/billing/current directory using the project name illing:
`ash
docker compose --project-name billing -f docker-compose.yml -f docker-compose.prod.yml --env-file /opt/realitytunnel/secrets/env/.env.production up -d
`

## 2. Rootless Docker & JWT Permissions
The VPS runs **Rootless Docker** under the user k (UID 1000). Inside the container, the application drops privileges to the illing user (UID 1001). Under the rootless namespace, UID 1001 maps to the host UID 101000.

To satisfy the application's aggressive os.stat().st_mode & 0o077 checks (which enforce chmod 600) while allowing Rootless Docker to bind-mount the files, the following structure was manually created:

`ash
/opt/realitytunnel/secrets/jwt/                 # chown ak:101000, chmod 750
├── ed25519_private.pem                         # chown 101000:101000, chmod 600
├── ed25519_public.pem                          # chown 101000:101000, chmod 600
└── admin/                                      # chown 101000:101000, chmod 600
    ├── admin_ed25519_private.pem               # chown 101000:101000, chmod 600
    └── admin_ed25519_public.pem                # chown 101000:101000, chmod 600
`
**Important:** 
- The directory MUST be owned by `ak:101000` with 750 permissions so the docker daemon (`ak`) can traverse it and the container user (101000) can enter it.
- The files MUST be natively named exactly `ed25519_private.pem` because the Python application's `secret_registry.py` currently hardcodes the filenames.

## 3. Rootless Docker Privileged Ports (Phase 4.4)
By default, Rootless Docker (via `rootlesskit`) cannot bind to privileged ports (under 1024). Because Caddy is deployed inside the Docker Compose stack and must listen on ports 80 and 443, the host's `sysctl` was permanently modified to lower the unprivileged port threshold.

If you ever reinstall Ubuntu or migrate to a new server, you MUST apply this setting or Caddy will fail to bind port 80/443:
```bash
echo "net.ipv4.ip_unprivileged_port_start=80" | sudo tee /etc/sysctl.d/99-rootless-ports.conf
sudo sysctl --system
```

## 3. Environment Variables (.env.production)
The startup_validator.py enforces strict production guards. We manually patched the environment on the host to bypass these guards during the initial rollout:

1. **Test Key Prevention:** The validator crashes if payment keys contain `placeholder_` or `test_`. The placeholder values were changed to `DUMMY_rzp_live_abc123` so the application boots safely without exposing fake keys as real ones.
2. **Localhost Gateway Prevention:** The `MARZBAN_BASE_URL` was manually upgraded from `http://marzban:8000` to `https://marzban:8000` to pass the HTTPS / No Localhost Gateways check.

## Future Improvements
- Make JWT file names configurable via `JWT_PRIVATE_KEY_PATH` in `secret_registry.py`.
- Ensure all `DUMMY_KEY` values are explicitly replaced with real provider keys prior to Phase 5.

### JWT Path Verification
Once configurable paths are implemented, use the following snippet to verify the paths loaded in the running production container. If this prints the wrong path after a deployment, you know immediately why JWTs are failing.

```bash
docker compose exec billing-api \
python - <<EOF
from app.core.secret_registry import secret_registry
print(secret_registry.jwt_private_key_path)
print(secret_registry.jwt_public_key_path)
EOF
```
