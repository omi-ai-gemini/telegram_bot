@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

if not exist "gateway_config.json" (
  echo [SETUP] gateway_config.json not found. Creating it now...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_gateway.ps1"
  if errorlevel 1 goto :failed
  echo.
  echo [IMPORTANT] Add the displayed LOCAL_AI_GATEWAY_SECRET to Render first.
  pause
)

where python >nul 2>nul
if not errorlevel 1 (
  python app.py
  goto :finished
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 app.py
  goto :finished
)

echo [ERROR] Python was not found.
goto :failed

:finished
if errorlevel 1 goto :failed
endlocal
exit /b 0

:failed
echo.
echo [ERROR] Local AI gateway failed to start.
pause
endlocal
exit /b 1
