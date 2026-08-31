# 🚀 MediKiosk — Quick Setup Script for Windows PowerShell
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🩺 MediKiosk Development Setup (Windows)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

# Check Python installation
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "❌ Python was not found in PATH! Please install Python 3.10+ and add it to PATH." -ForegroundColor Red
    exit 1
}

$pyVersion = & python --version 2>&1
Write-Host "✅ Found $pyVersion" -ForegroundColor Green

# Navigate to backend
Set-Location "$RootDir\backend"

# Create venv if not exists
if (-not (Test-Path "venv")) {
    Write-Host "📦 Creating Python virtual environment in backend/venv..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "✅ Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "ℹ️ Virtual environment backend/venv already exists." -ForegroundColor Gray
}

# Activate & Install requirements
Write-Host "⚙️ Upgrading pip and installing requirements..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\venv\Scripts\pip.exe" install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "❌ Error installing dependencies." -ForegroundColor Red
    exit 1
}

# Copy .env.example if .env doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "📝 Creating backend/.env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "⚠️ Remember to update backend/.env with your Supabase and API keys!" -ForegroundColor Yellow
} else {
    Write-Host "ℹ️ backend/.env already exists." -ForegroundColor Gray
}

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🎉 Setup Complete! To start the dev server run:" -ForegroundColor Green
Write-Host "   cd backend; .\venv\Scripts\python.exe -m uvicorn app.main:app --reload" -ForegroundColor White
Write-Host "   or: powershell .\scripts\run_backend.ps1" -ForegroundColor White
Write-Host "================================================" -ForegroundColor Cyan
