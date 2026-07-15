Add-Type -AssemblyName System.Security

function Unprotect-File($path) {
    if (-not (Test-Path $path)) { return $null }
    $encrypted = [System.IO.File]::ReadAllBytes($path)
    $decrypted = [System.Security.Cryptography.ProtectedData]::Unprotect($encrypted, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
    return [System.Text.Encoding]::UTF8.GetString($decrypted)
}

$secDir = "$env:LOCALAPPDATA\OverREALITY\Secure"
$accountId = Unprotect-File "$secDir\account_id.dat"
$masterToken = Unprotect-File "$secDir\master_token.dat"
$deviceGuid = Unprotect-File "$secDir\device_guid.dat"

Write-Host "=== STEP 1: CLIENT CREDENTIALS & LOGIN ==="
Write-Host "Account ID:  $accountId"
Write-Host "Device GUID: $deviceGuid"

$loginBody = @{
    account_id = $accountId
    master_token = $masterToken
    device_guid = $deviceGuid
} | ConvertTo-Json

Write-Host "`nSending POST https://api.stealthy.co.in/api/auth/login..."
$loginResp = Invoke-RestMethod -Uri "https://api.stealthy.co.in/api/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
Write-Host "Login Response status: Success"
Write-Host "Access Token (prefix): $($loginResp.access_token.Substring(0, 30))..."
Write-Host "Expires In: $($loginResp.expires_in)"

# Check heartbeat endpoint
$headers = @{
    "Authorization" = "Bearer $($loginResp.access_token)"
    "X-Device-Guid" = $deviceGuid
}
$heartbeatResp = Invoke-RestMethod -Uri "https://api.stealthy.co.in/api/devices/status" -Method Get -Headers $headers
Write-Host "`nHeartbeat Response (GET /api/devices/status):"
$heartbeatResp | ConvertTo-Json

Write-Host "`n=== STEP 2: PRODUCTION DATABASE STATE ==="
$sql = "SELECT account_id, device_guid, is_active, first_seen_at, last_seen_at FROM devices WHERE account_id = (SELECT id FROM accounts WHERE account_id = '$accountId');"
docker exec billing-server-db-1 psql -U billing -d billing -c $sql

Write-Host "`n=== STEP 3: DASHBOARD API RESPONSE ==="
$devicesApiResp = Invoke-RestMethod -Uri "https://api.stealthy.co.in/api/devices" -Method Get -Headers $headers
Write-Host "Raw JSON response of GET /api/devices:"
$devicesApiResp | ConvertTo-Json -Depth 5
