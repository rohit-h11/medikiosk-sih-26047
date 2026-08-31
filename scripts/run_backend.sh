#!/usr/bin/env bash
# ⚡ Run MediKiosk Backend (macOS / Linux)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$( dirname "$SCRIPT_DIR" )"
cd "$ROOT_DIR/backend"

if [ ! -f "venv/bin/python" ]; then
    echo "❌ Virtual environment not found! Run bash ./scripts/setup.sh first."
    exit 1
fi

echo "🚀 Starting MediKiosk FastAPI Backend at http://127.0.0.1:8000..."
./venv/bin/python -m uvicorn app.main:app --reload
