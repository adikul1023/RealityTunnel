<#
.SYNOPSIS
    Automated Production Rollback Script for RealityTunnel (PowerShell)
#>
param (
    [Parameter(Mandatory=$true)]
    [string]$TargetVersion
)

$ErrorActionPreference = "Stop"

Write-Host "── Initiating Emergency Rollback to $TargetVersion ──" -ForegroundColor Cyan

$env:APP_VERSION = $TargetVersion
$env:DOCKER_IMAGE = "ghcr.io/adikul1023/realitytunnel:$TargetVersion"

Write-Host "1. Pulling rollback image $($env:DOCKER_IMAGE)..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml pull billing-api

Write-Host "2. Restarting service with previous version..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml up -d --remove-orphans billing-api

Write-Host "3. Verifying health endpoint..." -ForegroundColor Yellow
$retries = 0
$maxRetries = 10
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
    Start-Sleep -Seconds 3
}

if (-not $healthy) {
    Write-Host "ERROR: Rollback health check failed!" -ForegroundColor Red
    docker compose -f docker-compose.prod.yml logs --tail=50 billing-api
    exit 1
}

Write-Host "4. Running smoke tests against rolled back instance..." -ForegroundColor Yellow
$env:TARGET_URL = "http://localhost:8080"
pytest tests/smoke/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Smoke tests failed after rollback!" -ForegroundColor Red
    exit 1
}

Write-Host "── Rollback to $TargetVersion Completed Successfully! ──" -ForegroundColor Green
