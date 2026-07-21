$ErrorActionPreference = "Stop"

Write-Host "2. Cleaning projects safely..."
dotnet clean RealityTunnel.csproj -c Release -p:Platform=x64
dotnet clean setup\setup.csproj -c Release -p:Platform=x64

Write-Host "3. Creating canonical output directories..."
$latestDir = "artifacts\latest"
$installerDir = "artifacts\installer"
if (Test-Path $latestDir) { Remove-Item -Recurse -Force $latestDir }
if (Test-Path $installerDir) { Remove-Item -Recurse -Force $installerDir }
New-Item -ItemType Directory -Force -Path $latestDir | Out-Null
New-Item -ItemType Directory -Force -Path $installerDir | Out-Null

Write-Host "4. Restoring and publishing RealityTunnel..."
dotnet restore RealityTunnel.csproj -p:Platform=x64
dotnet build RealityTunnel.csproj -c Release -p:Platform=x64
if ($LASTEXITCODE -ne 0) { throw "RealityTunnel build failed" }
dotnet publish RealityTunnel.csproj -c Release -p:Platform=x64 -r win-x64 --self-contained true --no-build
if ($LASTEXITCODE -ne 0) { throw "RealityTunnel build failed" }

Write-Host "4b. Restoring and publishing RealityTunnel.Helper..."
dotnet restore RealityTunnel.Helper\RealityTunnel.Helper.csproj
dotnet build RealityTunnel.Helper\RealityTunnel.Helper.csproj -c Release
if ($LASTEXITCODE -ne 0) { throw "RealityTunnel.Helper build failed" }
dotnet publish RealityTunnel.Helper\RealityTunnel.Helper.csproj -c Release -r win-x64 --self-contained true --no-build
if ($LASTEXITCODE -ne 0) { throw "RealityTunnel.Helper build failed" }

Write-Host "5. Copying RealityTunnel and Helper artifacts..."
$publishDir = "bin\x64\Release\net8.0-windows10.0.19041.0\win-x64\publish"
if (-Not (Test-Path $publishDir)) {
    $publishDir = "bin\Release\net8.0-windows10.0.19041.0\win-x64\publish"
}
Copy-Item -Path "$publishDir\*" -Destination $latestDir -Recurse -Force

$helperPublishDir = "RealityTunnel.Helper\bin\Release\net8.0-windows10.0.19041.0\win-x64\publish"
if (-Not (Test-Path $helperPublishDir)) {
    $helperPublishDir = "RealityTunnel.Helper\bin\x64\Release\net8.0-windows10.0.19041.0\win-x64\publish"
}
Copy-Item -Path "$helperPublishDir\*" -Destination $latestDir -Recurse -Force

Write-Host "Creating payload.zip for installer..."
if (Test-Path "setup\payload.zip") { Remove-Item -Force "setup\payload.zip" }
Compress-Archive -Path "$latestDir\*" -DestinationPath "setup\payload.zip" -Force

Write-Host "6. Building and publishing Installer..."
dotnet publish setup\setup.csproj -c Release -p:Platform=x64 -r win-x64 --self-contained true
if ($LASTEXITCODE -ne 0) { throw "Setup build failed" }

Write-Host "7. Copying Installer artifacts..."
$setupPublishDir = "setup\bin\x64\Release\net8.0-windows\win-x64\publish"
if (-Not (Test-Path $setupPublishDir)) {
    $setupPublishDir = "setup\bin\Release\net8.0-windows\win-x64\publish"
}
Copy-Item -Path "$setupPublishDir\setup.exe" -Destination $installerDir -Force

Write-Host "========================================="
Write-Host "Build complete!"
Write-Host "Main executable: $(Resolve-Path $latestDir\RealityTunnel.exe)"
Write-Host "Installer: $(Resolve-Path $installerDir\setup.exe)"
Write-Host "========================================="
