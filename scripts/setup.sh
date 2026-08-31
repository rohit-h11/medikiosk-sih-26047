#!/usr/bin/env bash
# MediKiosk — Quick Setup Script for macOS / Linux / Git Bash
set -e

CLEAN_MODE=false
for arg in "$@"; do
  if [ "$arg" == "--clean" ]; then
    CLEAN_MODE=true
  fi
done

echo -e "\033[0;36m================================================\033[0m"
echo -e "\033[0;36mMediKiosk Development Setup\033[0m"
echo -e "\033[0;36m================================================\033[0m"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$( dirname "$SCRIPT_DIR" )"

cd "$ROOT_DIR/backend"

# 1. Check Python executable
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
elif command -v py &>/dev/null; then
    PYTHON_CMD=py
else
    echo -e "\033[0;31m[X] Python 3 not found! Please install Python 3.10+.\033[0m"
    exit 1
fi

echo -e "\033[0;32m[OK] Found System Python: $($PYTHON_CMD --version)\033[0m"

# Function to locate python binary inside backend/venv across OSes
get_venv_python() {
    if [ -f "venv/bin/python" ]; then
        echo "venv/bin/python"
    elif [ -f "venv/Scripts/python.exe" ]; then
        echo "venv/Scripts/python.exe"
    elif [ -f "venv/Scripts/python" ]; then
        echo "venv/Scripts/python"
    else
        echo ""
    fi
}

VENV_PY=$(get_venv_python)

if [ "$CLEAN_MODE" = true ] && [ -d "venv" ]; then
    echo -e "\033[0;33m[!] --clean flag specified. Removing existing backend/venv...\033[0m"
    rm -rf venv
    VENV_PY=""
elif [ -d "venv" ] && [ -z "$VENV_PY" ]; then
    echo -e "\033[0;33m[!] Existing 'backend/venv' directory is incomplete or missing python executable.\033[0m"
    echo -e "\033[0;33m[!] Cleaning up corrupted virtual environment...\033[0m"
    rm -rf venv
fi

# 2. Create venv if needed
if [ -z "$VENV_PY" ]; then
    echo -e "\033[0;33m[+] Creating virtual environment in backend/venv...\033[0m"
    if ! $PYTHON_CMD -m venv venv; then
        echo -e "\033[0;31m[X] Failed to create virtual environment!\033[0m"
        echo -e "\033[0;33m[*] On Ubuntu/Debian, install venv support: sudo apt install python3-venv\033[0m"
        exit 1
    fi
    VENV_PY=$(get_venv_python)
    if [ -z "$VENV_PY" ]; then
        echo -e "\033[0;31m[X] Virtual environment creation finished but python binary was not found inside backend/venv!\033[0m"
        exit 1
    fi
    echo -e "\033[0;32m[OK] Virtual environment created.\033[0m"
else
    echo -e "\033[0;90m[i] Virtual environment backend/venv already exists and is valid.\033[0m"
fi

# 3. Install requirements
echo -e "\033[0;33m[+] Upgrading pip and installing requirements...\033[0m"
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -r requirements.txt

echo -e "\033[0;32m[OK] Dependencies installed successfully!\033[0m"

# 4. Copy .env
if [ ! -f ".env" ]; then
    echo -e "\033[0;33m[+] Creating backend/.env from .env.example...\033[0m"
    cp .env.example .env
    echo -e "\033[0;33m[!] Remember to update backend/.env with your Supabase & API keys!\033[0m"
else
    echo -e "\033[0;90m[i] backend/.env already exists.\033[0m"
fi

echo -e "\033[0;36m================================================\033[0m"
echo -e "\033[0;32mSetup Complete! To start the dev server run:\033[0m"
echo -e "   cd backend && $VENV_PY -m uvicorn app.main:app --reload"
echo -e "   or: bash ./scripts/run_backend.sh"
echo -e "\033[0;36m================================================\033[0m"
