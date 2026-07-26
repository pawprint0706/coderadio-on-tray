#Requires -Version 5.1
<#
.SYNOPSIS
  Build a Windows onedir release: dist/CodeRadioTray/ + bundled mpv.
#>
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

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

Write-Host ""
Write-Host "Build OK: $Dist"
Write-Host "Run:     $Exe"
Get-ChildItem $Dist -File | Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize
Write-Host "Bundle size (folder):" ((Get-ChildItem $Dist -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB).ToString('0.0') "MB"
