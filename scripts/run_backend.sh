#!/usr/bin/env bash
# Run MediKiosk Backend (macOS / Linux / Git Bash)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$( dirname "$SCRIPT_DIR" )"
cd "$ROOT_DIR/backend"

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

if [ -z "$VENV_PY" ]; then
    echo -e "\033[0;31m[X] Virtual environment not found or missing python executable!\033[0m"
    echo -e "\033[0;33m[!] Please run automated setup to fix/recreate your environment:\033[0m"
    echo -e "   bash ./scripts/setup.sh --clean"
    exit 1
fi

echo "[+] Starting MediKiosk FastAPI Backend at http://127.0.0.1:8000..."
"$VENV_PY" -m uvicorn app.main:app --reload
