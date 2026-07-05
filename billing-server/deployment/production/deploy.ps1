<#
.SYNOPSIS
    Production Deployment Script for RealityTunnel Billing Server (Windows PowerShell)
#>
$ErrorActionPreference = "Stop"

Write-Host "── Starting RealityTunnel Production Deployment ──" -ForegroundColor Cyan

# 1. Verify environment variables
if (-not $env:POSTGRES_PASSWORD -or -not $env:JWT_SECRET) {
    Write-Host "ERROR: Required production environment variables (POSTGRES_PASSWORD, JWT_SECRET) are not set!" -ForegroundColor Red
    exit 1
}

$env:ENVIRONMENT = "production"
$env:DEBUG = "false"
if (-not $env:APP_VERSION) { $env:APP_VERSION = "1.0.0" }

Write-Host "1. Creating pre-deployment database backup..." -ForegroundColor Yellow
try {
    python -m app.recovery.backup --create --reason "pre_deploy_$($env:APP_VERSION)"
} catch {
    Write-Host "Warning: Backup command failed or no local DB access; ensure external snapshots are active." -ForegroundColor Yellow
}

Write-Host "2. Pulling latest production Docker images..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml pull

Write-Host "3. Starting containers in production mode..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml up -d --remove-orphans

Write-Host "4. Waiting for health endpoint liveness..." -ForegroundColor Yellow
$retries = 0
$maxRetries = 12
$healthy = $false
while ($retries -lt $maxRetries) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8080/health" -TimeoutSec 5 -ErrorAction Stop
        if ($response.status -eq "ok") {
            $healthy = $true
            break
        }
    } catch {}
    $retries++
    Write-Host "Waiting for service... ($retries/$maxRetries)"
    Start-Sleep -Seconds 5
}

if (-not $healthy) {
    Write-Host "ERROR: Health check timed out! Dumping container logs..." -ForegroundColor Red
    docker compose -f docker-compose.prod.yml logs --tail=50 billing-api
    exit 1
}

Write-Host "5. Running automated smoke tests against production container..." -ForegroundColor Yellow
$env:TARGET_URL = "http://localhost:8080"
pytest tests/smoke/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Smoke tests failed after deployment!" -ForegroundColor Red
    exit 1
}

Write-Host "── Production Deployment Completed Successfully! ──" -ForegroundColor Green
