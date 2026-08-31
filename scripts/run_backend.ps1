# ⚡ Run MediKiosk Backend (Windows PowerShell)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location "$RootDir\backend"

if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "❌ Virtual environment not found! Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "🚀 Starting MediKiosk FastAPI Backend at http://127.0.0.1:8000..." -ForegroundColor Green
& ".\venv\Scripts\python.exe" -m uvicorn app.main:app --reload
