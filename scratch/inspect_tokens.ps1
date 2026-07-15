Add-Type -AssemblyName System.Security

function Unprotect-File($path) {
    if (-not (Test-Path $path)) { return $null }
    $encrypted = [System.IO.File]::ReadAllBytes($path)
    $decrypted = [System.Security.Cryptography.ProtectedData]::Unprotect($encrypted, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
    return [System.Text.Encoding]::UTF8.GetString($decrypted).Trim()
}

$secDir = "$env:LOCALAPPDATA\OverREALITY\Secure"
$tokensJson = Unprotect-File "$secDir\tokens.dat"
$deviceGuid = (Unprotect-File "$secDir\device_guid.dat").Trim('"').Trim()

$obj = $tokensJson | ConvertFrom-Json
$refreshToken = $obj.RefreshToken
Write-Host "Exchanging RefreshToken for fresh AccessToken with device_guid: $deviceGuid"

$exchangeBody = @{
    exchange_token = $refreshToken
    device_guid = $deviceGuid
} | ConvertTo-Json

$exResp = Invoke-RestMethod -Uri "https://api.stealthy.co.in/api/auth/exchange" -Method Post -Body $exchangeBody -ContentType "application/json"
$newAccessToken = $exResp.access_token

Write-Host "Exchange successful!"

$headers = @{
    "Authorization" = "Bearer $newAccessToken"
}
Write-Host "`n=== GET /api/devices RESPONSE ==="
$devs = Invoke-RestMethod -Uri "https://api.stealthy.co.in/api/devices" -Method Get -Headers $headers
$devs | ConvertTo-Json -Depth 5
