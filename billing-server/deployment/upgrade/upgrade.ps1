<#
.SYNOPSIS
    Automated Production Upgrade Script for RealityTunnel (PowerShell)
#>
param (
    [Parameter(Mandatory=$true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"

$oldVersion = if ($env:APP_VERSION) { $env:APP_VERSION } else { "1.0.0" }
Write-Host "── Starting RealityTunnel Upgrade from $oldVersion to $Version ──" -ForegroundColor Cyan

Write-Host "1. Creating pre-upgrade database backup..." -ForegroundColor Yellow
try {
    python -m app.recovery.backup --create --reason "pre_upgrade_$Version"
} catch {
    Write-Host "Warning: Backup command failed; ensure external DB snapshots exist." -ForegroundColor Yellow
}

$env:APP_VERSION = $Version
$env:DOCKER_IMAGE = "ghcr.io/adikul1023/realitytunnel:$Version"

Write-Host "2. Pulling target image $($env:DOCKER_IMAGE)..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml pull billing-api
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to pull image $($env:DOCKER_IMAGE). Aborting upgrade." -ForegroundColor Red
    exit 1
}

Write-Host "3. Recreating containers with new version..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml up -d --remove-orphans billing-api

Write-Host "4. Waiting for health check verification..." -ForegroundColor Yellow
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
    Write-Host "Waiting for upgraded service... ($retries/$maxRetries)"
    Start-Sleep -Seconds 5
}

if (-not $healthy) {
    Write-Host "ERROR: Upgrade failed health check! Automatically initiating rollback to $oldVersion..." -ForegroundColor Red
    .\deployment\rollback\rollback.ps1 -TargetVersion $oldVersion
    exit 1
}

Write-Host "5. Running smoke tests against upgraded container..." -ForegroundColor Yellow
$env:TARGET_URL = "http://localhost:8080"
pytest tests/smoke/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Smoke tests failed! Automatically initiating rollback to $oldVersion..." -ForegroundColor Red
    .\deployment\rollback\rollback.ps1 -TargetVersion $oldVersion
    exit 1
}

Write-Host "── Upgrade to $Version Completed Successfully! ──" -ForegroundColor Green
