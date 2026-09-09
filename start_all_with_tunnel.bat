@echo off
title MediKiosk Full Stack Launcher with Cloudflare Tunnel
echo =======================================================
echo   MediKiosk AI - Launching Backend, Frontend & Tunnel
echo =======================================================
echo.

REM Check if cloudflared is installed or present in folder
where cloudflared >nul 2>nul
if %errorlevel% neq 0 (
    if not exist "%~dp0cloudflared.exe" (
        echo [WARN] 'cloudflared' command not found in PATH!
        echo To install automatically, run: winget install Cloudflare.cloudflared
        echo Or place cloudflared.exe in this directory.
        echo.
    )
)

REM 1. Launch Backend in new window
echo [1/3] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "MediKiosk Backend (Uvicorn 8000)" cmd /k "cd /d %~dp0backend && .\venv\Scripts\activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

REM 2. Launch Frontend in new window
echo [2/3] Starting React Vite Frontend on http://localhost:3000 ...
start "MediKiosk Frontend (Vite 3000)" cmd /k "cd /d %~dp0frontend && npm run dev"

REM Wait 4 seconds for services to initialize
echo Waiting for servers to initialize...
timeout /t 4 /nobreak >nul

REM 3. Launch Cloudflare Tunnel in current window
echo.
echo [3/3] Exposing Vite (and proxied FastAPI backend) via Cloudflare Tunnel...
echo Copy the public https://*.trycloudflare.com URL below:
echo =======================================================
echo.

if exist "%~dp0cloudflared.exe" (
    "%~dp0cloudflared.exe" tunnel --url http://localhost:3000
) else (
    cloudflared tunnel --url http://localhost:3000
)

pause
