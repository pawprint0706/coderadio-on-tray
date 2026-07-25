$ErrorActionPreference = 'Stop'
# Dev launcher (Windows): run via dev_start.bat or `pwsh -File dev_start.ps1`.
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path .venv)) {
    Write-Host "Creating .venv ..."
    python -m venv .venv
}

Write-Host "Installing deps ..."
& .venv\Scripts\python.exe -m pip install -q -e .

Write-Host "Starting Code Radio Tray (Ctrl+C to quit) ..."
& .venv\Scripts\python.exe -m coderadio_tray --console