#Requires -Version 5.1
<#
.SYNOPSIS
  Fetch the pinned, checksummed portable mpv.exe used for Windows builds.
#>
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$PolicyPath = Join-Path $Root "packaging\mpv-versions.json"
$Policy = (Get-Content -Raw $PolicyPath | ConvertFrom-Json).windows
$DestDir = Join-Path $Root ".tools\mpv\extract"
$ArchiveDir = Join-Path $Root ".tools\mpv"
New-Item -ItemType Directory -Force -Path $DestDir, $ArchiveDir | Out-Null

$Existing = Join-Path $DestDir "mpv.exe"
$Marker = Join-Path $DestDir "mpv-version.json"
if ((Test-Path $Existing) -and (Test-Path $Marker)) {
    $Cached = Get-Content -Raw $Marker | ConvertFrom-Json
    if ($Cached.version -eq $Policy.version -and $Cached.sha256 -eq $Policy.sha256) {
        & $Existing --version *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Using validated cached mpv $($Policy.version): $Existing"
            exit 0
        }
        Write-Warning "Cached mpv cannot run; refreshing it."
    }
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

$Archive = Join-Path $ArchiveDir $Policy.archive
$ArchiveValid = $false
if (Test-Path $Archive) {
    $ArchiveHash = (Get-FileHash $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $ArchiveValid = $ArchiveHash -eq $Policy.sha256
}
if (-not $ArchiveValid) {
    Write-Host "Downloading pinned mpv $($Policy.version) ..."
    Invoke-WebRequest -Uri $Policy.url -OutFile $Archive -UseBasicParsing
}
$ArchiveHash = (Get-FileHash $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ArchiveHash -ne $Policy.sha256) {
    throw "mpv archive SHA256 mismatch. Expected $($Policy.sha256), got $ArchiveHash"
}
Write-Host "Verified SHA256: $ArchiveHash"

$ExtractTmp = Join-Path $ArchiveDir "_extract_tmp"
if (Test-Path $ExtractTmp) { Remove-Item -Recurse -Force $ExtractTmp }
New-Item -ItemType Directory -Force -Path $ExtractTmp | Out-Null
& $SevenZip x $Archive "-o$ExtractTmp" -y | Out-Null

$Found = Get-ChildItem $ExtractTmp -Recurse -Filter mpv.exe | Select-Object -First 1
if (-not $Found) { throw "mpv.exe not found inside archive." }
Remove-Item -Force -ErrorAction SilentlyContinue $Existing, $Marker, (Join-Path $DestDir "d3dcompiler_43.dll")
Copy-Item -Force $Found.FullName (Join-Path $DestDir "mpv.exe")
$Dll = Get-ChildItem $ExtractTmp -Recurse -Filter d3dcompiler_43.dll | Select-Object -First 1
if ($Dll) { Copy-Item -Force $Dll.FullName (Join-Path $DestDir "d3dcompiler_43.dll") }

Remove-Item -Recurse -Force $ExtractTmp
& $Existing --version *> $null
if ($LASTEXITCODE -ne 0) { throw "Downloaded mpv.exe failed its --version probe." }
@{
    version = [string]$Policy.version
    sha256 = [string]$Policy.sha256
} | ConvertTo-Json | Set-Content -Encoding UTF8 $Marker
Write-Host "mpv $($Policy.version) ready: $Existing"
