# MediKiosk - Launch both Backend and Frontend in a single command / terminal
param (
    [switch]$SeparateWindows
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

$venvPy = "$RootDir\backend\venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $venvPy = "python"
}

if ($SeparateWindows) {
    Write-Host "[+] Launching MediKiosk Backend in new window (http://127.0.0.1:8000)..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$RootDir\backend'; & '$venvPy' -m uvicorn app.main:app --reload"
    
    Write-Host "[+] Launching MediKiosk Frontend in new window (http://localhost:5173)..." -ForegroundColor Magenta
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$RootDir\frontend'; npm run dev"
    return
}

# Unified single-terminal launcher via npm concurrently
Set-Location $RootDir
npm run dev
