#Requires -Version 5.1
<#
.SYNOPSIS
  Download a portable mpv.exe into .tools/mpv/extract/ for bundling.
#>
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DestDir = Join-Path $Root ".tools\mpv\extract"
$ArchiveDir = Join-Path $Root ".tools\mpv"
New-Item -ItemType Directory -Force -Path $DestDir, $ArchiveDir | Out-Null

$Existing = Join-Path $DestDir "mpv.exe"
if (Test-Path $Existing) {
    Write-Host "Already present: $Existing"
    exit 0
}

$SevenZip = @(
    "${env:ProgramFiles}\7-Zip\7z.exe",
    "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $SevenZip) {
    Write-Host "7-Zip not found — trying winget install 7zip.7zip ..."
    winget install --id 7zip.7zip -e --accept-package-agreements --accept-source-agreements
    $SevenZip = @(
        "${env:ProgramFiles}\7-Zip\7z.exe",
        "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $SevenZip) { throw "7-Zip is required to extract mpv (mpv-*.7z)." }

Write-Host "Resolving latest shinchiro mpv-x86_64 asset ..."
$Release = Invoke-RestMethod -Uri "https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/releases/latest" -Headers @{
    "User-Agent" = "coderadio-on-tray-build"
}
$Asset = $Release.assets | Where-Object { $_.name -match '^mpv-x86_64-\d{8}-git-.*\.7z$' -and $_.name -notmatch 'v3|dev' } | Select-Object -First 1
if (-not $Asset) {
    $Asset = $Release.assets | Where-Object { $_.name -like 'mpv-x86_64-*.7z' -and $_.name -notmatch 'dev' } | Select-Object -First 1
}
if (-not $Asset) { throw "Could not find mpv-x86_64 *.7z in latest release." }

$Archive = Join-Path $ArchiveDir $Asset.name
Write-Host "Downloading $($Asset.name) ..."
Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $Archive -UseBasicParsing

$ExtractTmp = Join-Path $ArchiveDir "_extract_tmp"
if (Test-Path $ExtractTmp) { Remove-Item -Recurse -Force $ExtractTmp }
New-Item -ItemType Directory -Force -Path $ExtractTmp | Out-Null
& $SevenZip x $Archive "-o$ExtractTmp" -y | Out-Null

$Found = Get-ChildItem $ExtractTmp -Recurse -Filter mpv.exe | Select-Object -First 1
if (-not $Found) { throw "mpv.exe not found inside archive." }
Copy-Item -Force $Found.FullName (Join-Path $DestDir "mpv.exe")
$Dll = Get-ChildItem $ExtractTmp -Recurse -Filter d3dcompiler_43.dll | Select-Object -First 1
if ($Dll) { Copy-Item -Force $Dll.FullName (Join-Path $DestDir "d3dcompiler_43.dll") }

Remove-Item -Recurse -Force $ExtractTmp
Write-Host "mpv ready: $(Join-Path $DestDir 'mpv.exe')"
