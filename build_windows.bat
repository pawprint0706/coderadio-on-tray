@echo off
setlocal
cd /d "%~dp0"
echo Building Code Radio Tray (Windows onedir)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_windows.ps1"
set ERR=%ERRORLEVEL%
if %ERR% neq 0 (
  echo.
  echo Build FAILED with exit code %ERR%.
  pause
  exit /b %ERR%
)
echo.
echo Build finished. Output: dist\CodeRadioTray\CodeRadioTray.exe
pause
endlocal
