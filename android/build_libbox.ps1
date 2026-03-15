#Requires -Version 5
<#
.SYNOPSIS
    Builds libbox.aar from sing-box source and copies it to android/app/libs/.

.DESCRIPTION
    Prerequisites (must already be installed):
      - Go 1.24+         https://go.dev/dl/
    - Java 17 (JDK)    https://adoptium.net/
      - Android SDK+NDK  via Android Studio → SDK Manager → SDK Tools → NDK (Side by side)

    The script clones SagerNet/sing-box, installs sagernet's gomobile fork,
    builds libbox.aar and copies it here: android/app/libs/libbox.aar

    Run this script once before opening the Android project in Android Studio.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Config ────────────────────────────────────────────────────────────────────
$SING_BOX_VERSION = "v1.13.2"          # change to build a different version
$SING_BOX_REPO    = "https://github.com/SagerNet/sing-box.git"
$GOMOBILE_VERSION = "v0.1.12"

# Where to clone sing-box (sibling of this android/ directory so the build
# script can auto-copy via ../sing-box-for-android/app/libs/).
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir           # OverREALITY/
$CloneDir   = Join-Path $ProjectDir "sing-box-src"
$LibsDir    = Join-Path $ScriptDir "app\libs"

# ── Helper ────────────────────────────────────────────────────────────────────
function Check-Command($cmd) {
    return $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

function Die($msg) { Write-Error $msg; exit 1 }

function Get-JavaMajorFromVersionLine([string]$line) {
    # Handles both styles:
    #   "openjdk 17.0.12 ..."
    #   "java 24.0.2 ..."
    if ($line -match "\b(?:openjdk|java)\s+(\d+)") {
        return [int]$Matches[1]
    }
    return $null
}

function Try-UseLocalJdk17 {
    $candidates = @(
        "$env:ProgramFiles\Eclipse Adoptium",
        "$env:ProgramFiles\Temurin",
        "$env:ProgramFiles\Amazon Corretto",
        "$env:ProgramFiles\Microsoft",
        "$env:ProgramFiles\Zulu",
        "$env:ProgramFiles\Java"
    )

    foreach ($root in $candidates) {
        if (-not (Test-Path $root)) { continue }
        $jdkHomes = Get-ChildItem $root -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "17" }
        foreach ($jdkHome in $jdkHomes) {
            $javaExe = Join-Path $jdkHome.FullName "bin\java.exe"
            if (-not (Test-Path $javaExe)) { continue }
            $first = (& $javaExe --version 2>&1 | Select-Object -First 1)
            $major = Get-JavaMajorFromVersionLine $first
            if ($major -eq 17) {
                $env:JAVA_HOME = $jdkHome.FullName
                $env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
                return $first
            }
        }
    }

    return $null
}

# ── Preflight checks ──────────────────────────────────────────────────────────
Write-Host "==> Checking prerequisites..." -ForegroundColor Cyan

if (-not (Check-Command "go")) {
    Die "Go is not in PATH. Install from https://go.dev/dl/"
}
$goVer = (go version) -replace ".*go([\d.]+).*", '$1'
Write-Host "    go $goVer"

if (-not (Check-Command "java")) {
    Die "java is not in PATH. Install a JDK 17 from https://adoptium.net/"
}
$javaFirst = (java --version 2>&1 | Select-Object -First 1)
$javaMajor = Get-JavaMajorFromVersionLine $javaFirst

if ($javaMajor -ne 17) {
    $auto = Try-UseLocalJdk17
    if ($auto) {
        $javaFirst = $auto
        $javaMajor = 17
        Write-Host "    Switched to JAVA_HOME=$env:JAVA_HOME"
    }
}

if ($javaMajor -ne 17) {
    Die "JDK 17 is required by sing-box mobile build. Current: $javaFirst`nInstall JDK 17 and set JAVA_HOME, or keep it installed and rerun this script to auto-detect."
}
Write-Host "    java: $javaFirst"

# ANDROID_HOME / ANDROID_SDK_ROOT
$androidSdk = $env:ANDROID_HOME
if (-not $androidSdk) { $androidSdk = $env:ANDROID_SDK_ROOT }
if (-not $androidSdk) {
    $candidate = "$env:LOCALAPPDATA\Android\Sdk"
    if (Test-Path $candidate) { $androidSdk = $candidate }
}
if (-not $androidSdk) {
    Die "Android SDK not found. Set ANDROID_HOME or install Android Studio."
}
$env:ANDROID_HOME     = $androidSdk
$env:ANDROID_SDK_ROOT = $androidSdk
Write-Host "    ANDROID_HOME: $androidSdk"

# Check NDK exists
$ndkDir = Join-Path $androidSdk "ndk"
if (-not (Test-Path $ndkDir)) {
    Die "Android NDK not found at $ndkDir.`nInstall via Android Studio → SDK Manager → SDK Tools → NDK (Side by side)."
}
Write-Host "    NDK: found"

# ── Clone / update sing-box ───────────────────────────────────────────────────
Write-Host ""
Write-Host "==> Preparing sing-box source ($SING_BOX_VERSION)..." -ForegroundColor Cyan

if (-not (Test-Path $CloneDir)) {
    Write-Host "    Cloning $SING_BOX_REPO ..."
    git clone --depth 1 --branch $SING_BOX_VERSION $SING_BOX_REPO $CloneDir
} else {
    Write-Host "    $CloneDir already exists, checking out $SING_BOX_VERSION ..."
    Push-Location $CloneDir
    try {
        git fetch --tags --depth 1 origin $SING_BOX_VERSION
        git checkout $SING_BOX_VERSION
    } finally { Pop-Location }
}

# The build script auto-copies to ../sing-box-for-android/app/libs/ when that
# directory exists. We create a symlink (or directory) to trick it into copying
# directly into OUR project's libs folder.
$FakeAndroidDir = Join-Path $ProjectDir "sing-box-for-android\app\libs"
if (-not (Test-Path $FakeAndroidDir)) {
    Write-Host "    Creating libs redirect at $FakeAndroidDir ..."
    New-Item -ItemType Directory -Force -Path $FakeAndroidDir | Out-Null
}
if (-not (Test-Path $LibsDir)) {
    New-Item -ItemType Directory -Force -Path $LibsDir | Out-Null
}

# ── Install gomobile ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "==> Installing sagernet/gomobile $GOMOBILE_VERSION ..." -ForegroundColor Cyan
Push-Location $CloneDir
try {
    go install "github.com/sagernet/gomobile/cmd/gomobile@$GOMOBILE_VERSION"
    go install "github.com/sagernet/gomobile/cmd/gobind@$GOMOBILE_VERSION"
} finally { Pop-Location }

$gopath = (go env GOPATH)
$env:PATH = "$gopath\bin;$env:PATH"
if (-not (Check-Command "gomobile")) {
    Die "gomobile not found after install. Check that $(go env GOPATH)\bin is in PATH."
}
Write-Host "    gomobile: $(gomobile version 2>&1 | Select-Object -First 1)"

# ── Build libbox.aar ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "==> Building libbox.aar (this takes ~10-20 min the first time)..." -ForegroundColor Cyan

Push-Location $CloneDir
try {
    # GOPATH\bin must be on PATH so `gomobile` is found by the build script.
    go run ./cmd/internal/build_libbox -target android
} finally { Pop-Location }

# ── Locate output and copy ────────────────────────────────────────────────────
$builtAar  = Join-Path $CloneDir "libbox.aar"
$fakeAar   = Join-Path $FakeAndroidDir "libbox.aar"   # auto-copied by build script
$targetAar = Join-Path $LibsDir "libbox.aar"

if (Test-Path $fakeAar) {
    # Build script already copied it to our fake android dir → move to real libs
    Copy-Item $fakeAar $targetAar -Force
    Write-Host "    Copied from redirect path."
} elseif (Test-Path $builtAar) {
    Copy-Item $builtAar $targetAar -Force
    Write-Host "    Copied from build directory."
} else {
    Die "libbox.aar not found after build. Check build output above."
}

Write-Host ""
Write-Host "SUCCESS: libbox.aar → $targetAar" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open the android/ project in Android Studio"
Write-Host "  2. Sync Gradle (File → Sync Project with Gradle Files)"
Write-Host "  3. Build and run"
