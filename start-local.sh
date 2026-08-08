#!/usr/bin/env bash

set -e

echo "================================================================"
echo " Starting Verifact 100% Local DPDP-Compliant Clinical AI Pipeline "
echo "================================================================"

# Project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 1. Setup Backend Python Virtual Environment if missing
if [ ! -d "backend/venv" ]; then
    echo "Creating Python virtual environment in backend/venv..."
    python3 -m venv backend/venv
fi

echo "Activating virtual environment..."
source backend/venv/bin/activate

echo "Installing/verifying backend dependencies..."
pip install --quiet -r backend/requirements.txt || echo "Warning: Some python packages failed to install. Local fallbacks enabled."

# 2. Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "Shutting down local servers..."
    kill $(jobs -p) 2>/dev/null || true
    echo "Shutdown complete."
}
trap cleanup EXIT INT TERM

# 3. Start FastAPI Backend Server
echo "Starting FastAPI Backend Server on http://localhost:8000..."
uvicorn --app-dir backend main:app --reload --port 8000 &
BACKEND_PID=$!

sleep 2

# 4. Start Frontend Dev Server
echo "Starting TanStack Start / Vite Frontend Server..."
npm run dev

wait $BACKEND_PID
