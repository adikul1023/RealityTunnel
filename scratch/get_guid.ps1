Add-Type -AssemblyName System.Security
$path = [System.IO.Path]::Combine($env:LOCALAPPDATA, 'OverREALITY', 'Secure', 'device_guid.dat')
if (Test-Path $path) {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $dec = [System.Security.Cryptography.ProtectedData]::Unprotect($bytes, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
    $guid = [System.Text.Encoding]::UTF8.GetString($dec)
    Write-Host "WINDOWS_CLIENT_DEVICE_GUID: $guid"
} else {
    Write-Host "WINDOWS_CLIENT_DEVICE_GUID: NOT_FOUND"
}
