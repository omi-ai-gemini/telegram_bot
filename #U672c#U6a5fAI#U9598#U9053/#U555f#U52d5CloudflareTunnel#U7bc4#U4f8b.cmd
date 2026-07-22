@echo off
setlocal
cd /d "%~dp0"
cloudflared tunnel run telemini-ai
if errorlevel 1 pause
endlocal
