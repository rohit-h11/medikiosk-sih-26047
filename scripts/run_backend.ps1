# Run MediKiosk Backend (Windows PowerShell)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location "$RootDir\backend"

$venvPyPath = ".\venv\Scripts\python.exe"

if (-not (Test-Path $venvPyPath)) {
    Write-Host "[X] Virtual environment python binary not found at '$venvPyPath'!" -ForegroundColor Red
    Write-Host "[!] Please run automated setup to fix/recreate your environment:" -ForegroundColor Yellow
    Write-Host "   powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Clean" -ForegroundColor White
    exit 1
}

Write-Host "[+] Starting MediKiosk FastAPI Backend at http://127.0.0.1:8000..." -ForegroundColor Green
& $venvPyPath -m uvicorn app.main:app --reload
