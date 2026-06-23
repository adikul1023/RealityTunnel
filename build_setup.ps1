# OverREALITY — setup.exe Packaging Script
# This script bundles the compiled client files and builds a single-file installer.

$ErrorActionPreference = "Stop"

# Paths
$rootDir = Get-Item "."
$publishDir = Join-Path $rootDir "bin\x64\Release\net8.0-windows10.0.19041.0\win-x64\publish"
$setupDir = Join-Path $rootDir "setup"
$tempPayloadDir = Join-Path $setupDir "temp_payload"
$zipPath = Join-Path $setupDir "payload.zip"
$icoPath = Join-Path $setupDir "app.ico"
$outputExe = Join-Path $rootDir "setup.exe"

Write-Host "--- OverREALITY Setup Builder ---" -ForegroundColor Cyan

# 1. Validate required files in publish folder
$requiredFiles = @(
    "app.ico",
    "config.template.json",
    "geoip.dat",
    "geosite.dat",
    "libcronet.dll",
    "RealityTunnel.exe",
    "sing-box.exe",
    "wintun.dll"
)

Write-Host "Verifying files in $publishDir..." -ForegroundColor Gray
foreach ($file in $requiredFiles) {
    $filePath = Join-Path $publishDir $file
    if (-not (Test-Path $filePath)) {
        Write-Error "Required file missing: $filePath. Please run publish first."
    }
}
Write-Host "All required files found!" -ForegroundColor Green

# 2. Re-create temp folder for payload
if (Test-Path $tempPayloadDir) {
    Remove-Item $tempPayloadDir -Recurse -Force
}
New-Item -Path $tempPayloadDir -ItemType Directory | Out-Null

# 3. Copy files to temp folder
Write-Host "Packaging client files..." -ForegroundColor Gray
foreach ($file in $requiredFiles) {
    Copy-Item (Join-Path $publishDir $file) (Join-Path $tempPayloadDir $file) -Force
}

# 4. Zip the payload folder
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Write-Host "Creating compressed archive..." -ForegroundColor Gray
Compress-Archive -Path (Join-Path $tempPayloadDir "*") -DestinationPath $zipPath -Force

# 5. Copy app.ico to setup folder for compilation icon
Copy-Item (Join-Path $publishDir "app.ico") $icoPath -Force

# 6. Clean up temporary payload folder (we only need payload.zip for compilation)
Remove-Item $tempPayloadDir -Recurse -Force

# 7. Compile the setup project as single-file exe
Write-Host "Compiling setup project..." -ForegroundColor Gray
dotnet publish (Join-Path $setupDir "setup.csproj") -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true

# 8. Copy the final setup.exe to root
$builtExe = Join-Path $setupDir "bin\Release\net8.0-windows\win-x64\publish\setup.exe"
if (-not (Test-Path $builtExe)) {
    $builtExe = Join-Path $setupDir "bin\x64\Release\net8.0-windows\win-x64\publish\setup.exe"
}
if (-not (Test-Path $builtExe)) {
    $builtExe = Join-Path $setupDir "bin\win-x64\publish\setup.exe"
}

if (-not (Test-Path $builtExe)) {
    Write-Error "Could not find built setup.exe. Build may have failed."
}

Copy-Item $builtExe $outputExe -Force

# 9. Cleanup setup resources to keep directory clean
Remove-Item $zipPath -Force
Remove-Item $icoPath -Force

Write-Host "`nSuccessfully created self-contained installer: $outputExe" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
