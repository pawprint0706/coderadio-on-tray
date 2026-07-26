@echo off
setlocal
cd /d "%~dp0"
echo Building Code Radio Tray (Windows onedir + per-user setup)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_windows.ps1"
set ERR=%ERRORLEVEL%
if %ERR% neq 0 (
  echo.
  echo Build FAILED with exit code %ERR%.
  pause
  exit /b %ERR%
)
echo.
echo Build finished.
echo   Portable:  dist\CodeRadioTray\CodeRadioTray.exe
echo   Installer: dist\CodeRadioTray-*-win64-setup.exe
echo   Installs to: %%LOCALAPPDATA%%\Programs\CodeRadioTray
pause
endlocal
