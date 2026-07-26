#Requires -Version 5.1
<#
.SYNOPSIS
  Build Windows onedir + per-user Inno Setup installer (not Program Files).

.OUTPUTS
  dist\CodeRadioTray\                          — portable onedir
  dist\CodeRadioTray-<ver>-win64-setup.exe     — setup wizard (user install)
#>
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

function Find-ISCC {
    $candidates = @(
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 7\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Ensure-InnoSetup {
    $iscc = Find-ISCC
    if ($iscc) { return [string]$iscc }

    Write-Host "Inno Setup not found — installing via winget (JRSoftware.InnoSetup) ..."
    $null = winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
    # winget may finish before PATH / shortcuts settle
    Start-Sleep -Seconds 2
    $iscc = Find-ISCC
    if (-not $iscc) {
        throw "ISCC.exe still not found after winget install. Install Inno Setup 6+ and re-run."
    }
    return [string]$iscc
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating .venv ..."
    python -m venv .venv
    $VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
}

Write-Host "Installing package + PyInstaller ..."
& $VenvPython -m pip install -q -e ".[dev]"

$MpvSrc = Join-Path $Root ".tools\mpv\extract\mpv.exe"
if (-not (Test-Path $MpvSrc)) {
    $Fetch = Join-Path $PSScriptRoot "fetch_mpv_windows.ps1"
    Write-Host "mpv not found at $MpvSrc — running fetch script ..."
    & $Fetch
}
if (-not (Test-Path $MpvSrc)) {
    throw "mpv.exe missing. Place it at .tools\mpv\extract\mpv.exe or run scripts\fetch_mpv_windows.ps1"
}

$Spec = Join-Path $Root "packaging\coderadio_tray.spec"
Write-Host "Running PyInstaller ..."
& $VenvPython -m PyInstaller --noconfirm --clean $Spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }

$Dist = Join-Path $Root "dist\CodeRadioTray"
$MpvDestDir = Join-Path $Dist "mpv"
New-Item -ItemType Directory -Force -Path $MpvDestDir | Out-Null
Copy-Item -Force $MpvSrc (Join-Path $MpvDestDir "mpv.exe")

$Dll = Join-Path $Root ".tools\mpv\extract\d3dcompiler_43.dll"
if (Test-Path $Dll) {
    Copy-Item -Force $Dll (Join-Path $MpvDestDir "d3dcompiler_43.dll")
}

$Exe = Join-Path $Dist "CodeRadioTray.exe"
if (-not (Test-Path $Exe)) { throw "Missing output: $Exe" }

$Version = (& $VenvPython -c "from coderadio_tray import __version__; print(__version__)").Trim()
Write-Host "App version: $Version"

Write-Host "Building per-user installer (Inno Setup) ..."
$Iscc = Ensure-InnoSetup
$Iss = Join-Path $Root "packaging\windows\CodeRadioTray.iss"
& $Iscc "/DMyAppVersion=$Version" $Iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed ($LASTEXITCODE)" }

$Setup = Join-Path $Root "dist\CodeRadioTray-$Version-win64-setup.exe"
if (-not (Test-Path $Setup)) { throw "Missing installer: $Setup" }

Write-Host ""
Write-Host "Build OK"
Write-Host "  Onedir:    $Dist"
Write-Host "  Installer: $Setup  (installs to %LOCALAPPDATA%\Programs\CodeRadioTray)"
Write-Host "  Onedir size:" ((Get-ChildItem $Dist -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB).ToString('0.0') "MB"
Write-Host "  Setup size:" ([math]::Round((Get-Item $Setup).Length / 1MB, 1)) "MB"
