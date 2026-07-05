<#
.SYNOPSIS
    Staging Deployment Script for RealityTunnel Billing Server (PowerShell)
#>
$ErrorActionPreference = "Stop"

Write-Host "── Starting RealityTunnel Staging Deployment ──" -ForegroundColor Cyan

$env:ENVIRONMENT = "staging"
$env:DEBUG = "true"
if (-not $env:APP_VERSION) { $env:APP_VERSION = "1.0.0-rc.1" }
if (-not $env:POSTGRES_DB) { $env:POSTGRES_DB = "billing_staging" }

Write-Host "1. Building and starting containers in staging mode..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans

Write-Host "2. Waiting for health endpoint liveness..." -ForegroundColor Yellow
$retries = 0
$maxRetries = 10
$healthy = $false
while ($retries -lt $maxRetries) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8080/health" -TimeoutSec 5 -ErrorAction Stop
        if ($response.version) {
            $healthy = $true
            break
        }
    } catch {}
    $retries++
    Start-Sleep -Seconds 3
}

if (-not $healthy) {
    Write-Host "ERROR: Staging health check timed out! Dumping container logs..." -ForegroundColor Red
    docker compose -f docker-compose.prod.yml logs --tail=50 billing-api
    exit 1
}

Write-Host "3. Running smoke tests against staging..." -ForegroundColor Yellow
$env:TARGET_URL = "http://localhost:8080"
pytest tests/smoke/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Smoke tests failed on staging!" -ForegroundColor Red
    exit 1
}

Write-Host "── Staging Deployment & Verification Completed! ──" -ForegroundColor Green
