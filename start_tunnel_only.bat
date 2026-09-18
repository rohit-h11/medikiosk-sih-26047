@echo off
title MediKiosk Cloudflare Tunnel
echo =======================================================
echo   MediKiosk AI - Exposing Local Port 3000 to Internet
echo =======================================================
echo.

if exist "%~dp0cloudflared.exe" (
    "%~dp0cloudflared.exe" tunnel --url http://localhost:3000
) else (
    cloudflared tunnel --url http://localhost:3000
)

pause
