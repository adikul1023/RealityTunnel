Add-Type -AssemblyName System.Security
$dir = [System.IO.Path]::Combine($env:LOCALAPPDATA, 'OverREALITY', 'Secure')

function Unprotect-File($name) {
    $path = [System.IO.Path]::Combine($dir, $name)
    if (Test-Path $path) {
        $bytes = [System.IO.File]::ReadAllBytes($path)
        $dec = [System.Security.Cryptography.ProtectedData]::Unprotect($bytes, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
        return [System.Text.Encoding]::UTF8.GetString($dec)
    }
    return "NOT_FOUND"
}

Write-Host "DEVICE_GUID: " (Unprotect-File 'device_guid.dat')
Write-Host "DEVICE_NAME: " (Unprotect-File 'device_name.dat')
Write-Host "ACCOUNT_ID:  " (Unprotect-File 'account_id.dat')
Write-Host "TOKENS:      " (Unprotect-File 'tokens.dat')
