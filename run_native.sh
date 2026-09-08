#!/bin/bash
# LogiScan Native Start — Robust Version
# Usage: ./run_native.sh [--dev]
set -e

MODE="${1:-prod}"
if [ "$MODE" = "--dev" ]; then
    MODE="dev"
fi

PID_FILE_BACKEND="/tmp/logiscan_backend.pid"
PID_FILE_FRONTEND="/tmp/logiscan_frontend.pid"

cleanup() {
    echo "Shutting down LogiScan..."
    for pid_file in "$PID_FILE_BACKEND" "$PID_FILE_FRONTEND"; do
        if [ -f "$pid_file" ]; then
            kill $(cat "$pid_file") 2>/dev/null || true
            rm -f "$pid_file"
        fi
    done
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Clean up old PID files
echo "Cleaning up old LogiScan instances..."
for pid_file in "$PID_FILE_BACKEND" "$PID_FILE_FRONTEND"; do
    if [ -f "$pid_file" ]; then
        old_pid=$(cat "$pid_file")
        if kill -0 "$old_pid" 2>/dev/null; then
            kill "$old_pid" 2>/dev/null || true
            sleep 1
        fi
        rm -f "$pid_file"
    fi
done

# Activate Python venv
PYTHON=python3
ACTIVATE="venv/bin/activate"

if [ ! -f "$ACTIVATE" ]; then
    python3 -m venv venv
fi
source "$ACTIVATE"

# Install Python dependencies
pip install -q -r backend/requirements.txt 2>/dev/null || pip install -r backend/requirements.txt

wait_for_backend() {
    echo "Waiting for backend..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:8000/api/v1/health/live >/dev/null 2>&1; then
            echo "Backend ready."
            return 0
        fi
        sleep 1
    done
    echo "Backend did not become ready in time."
    return 1
}

if [ "$MODE" = "dev" ]; then
    # Development mode: Vite dev server + backend
    echo "Starting backend (API server)..."
    uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 &
    echo $! > "$PID_FILE_BACKEND"
    wait_for_backend

    echo "Starting Vite dev server..."
    (cd frontend && npm install --silent && npm run dev) &
    echo $! > "$PID_FILE_FRONTEND"

    echo "==========================================="
    echo "  LogiScan v1.2 — DEV MODE"
    echo "  SPA:  http://localhost:5173"
    echo "  API:  http://localhost:8000/api/v1/analyze"
    echo "  Docs: http://localhost:8000/docs"
    echo "==========================================="
else
    # Production mode: build frontend and serve from backend
    echo "Installing frontend dependencies..."
    (cd frontend && npm install --silent)

    if [ ! -d "frontend/dist" ]; then
        echo "Building React frontend..."
        (cd frontend && npm run build)
    fi

    echo "Starting backend (serves API + SPA at http://localhost:8000)..."
    uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 2>>backend_startup.log &
    echo $! > "$PID_FILE_BACKEND"
    wait_for_backend

    echo "==========================================="
    echo "  LogiScan v1.2 (Premium XAI) is running!"
    echo "  SPA:  http://localhost:8000"
    echo "  API:  http://localhost:8000/api/v1/analyze"
    echo "  Docs: http://localhost:8000/docs"
    echo "==========================================="
fi

wait
