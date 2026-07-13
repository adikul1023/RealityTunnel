#!/bin/bash
set -e

echo "=== Production Verification Report ==="
echo ""

echo "[1/6] Host Health & Resources"
uptime
load=$(cat /proc/loadavg | awk '{print $1}')
echo "Load Average (1m): $load"
date -u
free -m
df -h /

echo ""
echo "[2/6] Docker & Network Status"
systemctl is-active docker || echo "Docker daemon is inactive!"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "Networks:"
docker network ls --filter "name=billing"

echo ""
echo "[3/6] WireGuard Status"
wg show || echo "WireGuard not active or configured"

echo ""
echo "[4/6] HTTP Endpoints & Security Headers"
echo "Testing security headers on https://api.stealthy.co.in..."
curl -s -I https://api.stealthy.co.in | grep -E -i "strict-transport-security|x-frame-options|x-content-type-options|referrer-policy|permissions-policy" || echo "Missing security headers!"

echo ""
echo "Testing /livez (Expect 200)"
curl -s -o /dev/null -w "%{http_code}\n" https://api.stealthy.co.in/livez

echo "Testing /readyz (Expect 403)"
curl -s -o /dev/null -w "%{http_code}\n" https://api.stealthy.co.in/readyz

echo "Testing /metrics (Expect 401)"
curl -s -o /dev/null -w "%{http_code}\n" https://api.stealthy.co.in/metrics

echo ""
echo "[5/6] TLS Validation (using testssl.sh)"
docker run --rm -t drwetter/testssl.sh --quiet --protocols --server-preference https://api.stealthy.co.in || echo "testssl.sh failed"

echo ""
echo "[6/6] Logs (Last 5 mins)"
docker logs --since 5m billing-caddy-1 | tail -n 5

echo "=== End of Report ==="
