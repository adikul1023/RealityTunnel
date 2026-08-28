param (
    [string]$BillingServerUrl = "http://localhost:8000",
    [string]$BootstrapToken = "dummy_token",
    [string]$AgentAppsettingsPath = "..\..\..\VpnHood\src\Apps\Server.Net\appsettings.json"
)

Write-Host "VPNHood Node Bootstrap Script"
Write-Host "============================="

# 1. Exchange Bootstrap Token for Agent Secret
Write-Host "1. Exchanging Bootstrap Token for Agent Secret..."
$headers = @{ "Bootstrap-Token" = $BootstrapToken }
$bootstrapResponse = Invoke-RestMethod -Uri "$BillingServerUrl/api/agent/bootstrap" -Method Post -Headers $headers -ErrorAction Stop

$nodeId = $bootstrapResponse.node_id
$agentSecret = $bootstrapResponse.agent_secret

Write-Host "Successfully bootstrapped Node ID: $nodeId"

# 2. Update appsettings.json for the Agent
Write-Host "2. Updating appsettings.json with Agent Secret..."
$config = Get-Content $AgentAppsettingsPath -Raw | ConvertFrom-Json

if ($null -eq $config.HttpAccessManager) {
    $config | Add-Member -MemberType NoteProperty -Name "HttpAccessManager" -Value @{}
}
$config.HttpAccessManager = @{
    Authorization = "Bearer $agentSecret"
    BaseUrl = "$BillingServerUrl/api/agent/"
}

$config | ConvertTo-Json -Depth 10 | Set-Content $AgentAppsettingsPath
Write-Host "Agent appsettings updated successfully."

# 3. Generate a Self-Signed PFX Certificate
Write-Host "3. Generating Self-Signed Certificate..."
$certName = "CN=VPNHood-Node-$nodeId"
$cert = New-SelfSignedCertificate -DnsName "localhost" -CertStoreLocation "cert:\CurrentUser\My" -Subject $certName -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddYears(1)

$pfxPath = "$env:TEMP\vpnhood_$nodeId.pfx"
$certBytes = $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Pfx)
[System.IO.File]::WriteAllBytes($pfxPath, $certBytes)

$pfxBytes = [System.IO.File]::ReadAllBytes($pfxPath)
$pfxBase64 = [Convert]::ToBase64String($pfxBytes)

# Clean up temp file
Remove-Item $pfxPath

# 4. Upload PFX to Billing Server
Write-Host "4. Uploading PFX to Billing Server..."
$authHeaders = @{
    "Authorization" = "Bearer $agentSecret"
    "Content-Type" = "application/json"
}
$certBody = @{
    "pfx_base64" = $pfxBase64
} | ConvertTo-Json

Invoke-RestMethod -Uri "$BillingServerUrl/api/agent/register-cert" -Method Post -Headers $authHeaders -Body $certBody | Out-Null
Write-Host "Certificate successfully uploaded and registered."

Write-Host "Bootstrap Complete. You may now start the VPNHood Server."
