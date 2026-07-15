Add-Type -AssemblyName System.Security

function Unprotect-File($path) {
    if (-not (Test-Path $path)) { return $null }
    $encrypted = [System.IO.File]::ReadAllBytes($path)
    $decrypted = [System.Security.Cryptography.ProtectedData]::Unprotect($encrypted, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
    $str = [System.Text.Encoding]::UTF8.GetString($decrypted).Trim()
    return $str.Trim('"').Trim()
}

$secDir = "$env:LOCALAPPDATA\OverREALITY\Secure"
$accountId = Unprotect-File "$secDir\account_id.dat"
$masterToken = Unprotect-File "$secDir\master_token.dat"
$deviceGuid = Unprotect-File "$secDir\device_guid.dat"

Write-Host "Account ID:  [$accountId]"
Write-Host "Device GUID: [$deviceGuid]"

$loginBody = @{
    account_id = $accountId
    master_token = $masterToken
    device_guid = $deviceGuid
} | ConvertTo-Json

$loginResp = Invoke-RestMethod -Uri "https://api.stealthy.co.in/api/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
Write-Host "Login Status: Success"
$token = $loginResp.access_token

$headers = @{
    "Authorization" = "Bearer $token"
}

Write-Host "`n=== GET /api/devices RESPONSE ==="
$devsResp = Invoke-RestMethod -Uri "https://api.stealthy.co.in/api/devices" -Method Get -Headers $headers
$devsResp | ConvertTo-Json -Depth 5
