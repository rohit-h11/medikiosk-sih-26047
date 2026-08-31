#!/usr/bin/env bash
# 🚀 MediKiosk — Quick Setup Script for macOS / Linux
set -e

echo -e "\033[0;36m================================================\033[0m"
echo -e "\033[0;36m🩺 MediKiosk Development Setup (Mac / Linux)\033[0m"
echo -e "\033[0;36m================================================\033[0m"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$( dirname "$SCRIPT_DIR" )"

cd "$ROOT_DIR/backend"

# Check Python
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    echo -e "\033[0;31m❌ Python 3 not found! Please install Python 3.10+.\033[0m"
    exit 1
fi

echo -e "\033[0;32m✅ Found $($PYTHON_CMD --version)\033[0m"

# Create venv
if [ ! -d "venv" ]; then
    echo -e "\033[0;33m📦 Creating virtual environment in backend/venv...\033[0m"
    $PYTHON_CMD -m venv venv
    echo -e "\033[0;32m✅ Virtual environment created.\033[0m"
else
    echo -e "\033[0;90mℹ️ backend/venv already exists.\033[0m"
fi

# Install requirements
echo -e "\033[0;33m⚙️ Upgrading pip and installing requirements...\033[0m"
./venv/bin/python -m pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo -e "\033[0;32m✅ Dependencies installed successfully!\033[0m"

# Copy .env
if [ ! -f ".env" ]; then
    echo -e "\033[0;33m📝 Creating backend/.env from .env.example...\033[0m"
    cp .env.example .env
    echo -e "\033[0;33m⚠️ Remember to update backend/.env with your Supabase & API keys!\033[0m"
else
    echo -e "\033[0;90mℹ️ backend/.env already exists.\033[0m"
fi

echo -e "\033[0;36m================================================\033[0m"
echo -e "\033[0;32m🎉 Setup Complete! To start the dev server run:\033[0m"
echo -e "   cd backend && ./venv/bin/uvicorn app.main:app --reload"
echo -e "   or: bash ./scripts/run_backend.sh"
echo -e "\033[0;36m================================================\033[0m"
