param(
    [switch]$Clean
)

# MediKiosk — Quick Setup Script for Windows PowerShell
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "MediKiosk Development Setup (Windows)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

# 1. Check Python installation (prefer 'python', fallback to 'py')
$pyExe = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyExe = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pyExe = "py"
} else {
    Write-Host "[X] Python was not found in PATH! Please install Python 3.10+ and add it to PATH." -ForegroundColor Red
    exit 1
}

$pyVersion = & $pyExe --version 2>&1
Write-Host "[OK] Found System Python: $pyVersion" -ForegroundColor Green

# 2. Navigate to backend
Set-Location "$RootDir\backend"

$venvPyPath = ".\venv\Scripts\python.exe"
$venvPipPath = ".\venv\Scripts\pip.exe"

# Helper function to remove broken/old venv
function Remove-VenvDirectory {
    if (Test-Path "venv") {
        Remove-Item -Recurse -Force "venv" -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 1000
        if (Test-Path "venv") {
            cmd /c "rmdir /s /q venv" 2>$null
        }
    }
}

# If -Clean flag is passed or venv folder exists without python.exe, clean it up
if ($Clean -and (Test-Path "venv")) {
    Write-Host "[!] -Clean flag specified. Removing existing backend/venv..." -ForegroundColor Yellow
    Remove-VenvDirectory
} elseif ((Test-Path "venv") -and (-not (Test-Path $venvPyPath))) {
    Write-Host "[!] Existing 'backend/venv' directory is incomplete or missing '$venvPyPath'." -ForegroundColor Yellow
    Write-Host "[!] Cleaning up corrupted virtual environment..." -ForegroundColor Yellow
    Remove-VenvDirectory
}

# 3. Create venv if needed
if (-not (Test-Path $venvPyPath)) {
    Write-Host "[+] Creating Python virtual environment in backend/venv..." -ForegroundColor Yellow
    & $pyExe -m venv venv
    Start-Sleep -Milliseconds 1000
    
    if (-not (Test-Path $venvPyPath)) {
        Write-Host "[X] Failed to create virtual environment in backend/venv!" -ForegroundColor Red
        Write-Host "    Please verify your Python installation has 'venv' support." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Virtual environment created successfully." -ForegroundColor Green
} else {
    Write-Host "[i] Virtual environment backend/venv already exists and is valid." -ForegroundColor Gray
}

# 4. Activate & Install requirements
Write-Host "[+] Upgrading pip and installing requirements..." -ForegroundColor Yellow
& $venvPyPath -m pip install --upgrade pip
& $venvPyPath -m pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "[X] Error installing dependencies." -ForegroundColor Red
    exit 1
}

# 5. Copy .env.example if .env doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "[+] Creating backend/.env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[!] Remember to update backend/.env with your Supabase and API keys!" -ForegroundColor Yellow
} else {
    Write-Host "[i] backend/.env already exists." -ForegroundColor Gray
}

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Setup Complete! To start the dev server run:" -ForegroundColor Green
Write-Host "   cd backend; .\venv\Scripts\python.exe -m uvicorn app.main:app --reload" -ForegroundColor White
Write-Host "   or: powershell .\scripts\run_backend.ps1" -ForegroundColor White
Write-Host "================================================" -ForegroundColor Cyan
