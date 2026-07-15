Add-Type -AssemblyName System.Security

function Unprotect-File($path) {
    if (-not (Test-Path $path)) { return $null }
    $encrypted = [System.IO.File]::ReadAllBytes($path)
    $decrypted = [System.Security.Cryptography.ProtectedData]::Unprotect($encrypted, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
    return [System.Text.Encoding]::UTF8.GetString($decrypted)
}

$secDir = "$env:LOCALAPPDATA\OverREALITY\Secure"
$a = Unprotect-File "$secDir\account_id.dat"
$m = Unprotect-File "$secDir\master_token.dat"
$d = Unprotect-File "$secDir\device_guid.dat"

Write-Host "A: [$a] len=$($a.Length)"
Write-Host "M: [$m] len=$($m.Length)"
Write-Host "D: [$d] len=$($d.Length)"
