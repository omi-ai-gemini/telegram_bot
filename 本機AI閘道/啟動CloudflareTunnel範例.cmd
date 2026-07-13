@echo off
chcp 65001 >nul
REM 把 telemini-ai 改成你建立的 Cloudflare Tunnel 名稱。
cloudflared tunnel run telemini-ai
pause
