#!/usr/bin/env bash
set -e

echo "======================================"
echo "Catalyst: Checking dependencies..."
echo "======================================"

if ! command -v uv &> /dev/null; then
    echo "Error: 'uv' is not installed."
    echo "Please install it: https://github.com/astral-sh/uv"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "Error: 'npm' is not installed."
    echo "Please install Node.js and npm: https://nodejs.org/"
    exit 1
fi

# Check mngr's system deps (tmux, ssh, git, jq) before touching uv/npm.
# This only matters for tasks created with framework `mngr-claude` /
# `mngr-antigravity`; direct `claude` framework tasks don't strictly need
# mngr's deps. But all options are in the dropdown at runtime, so we check
# up-front rather than waiting for the first mngr task to crash.
if ! uv run mngr dependencies; then
    echo ""
    echo "Some mngr-required system dependencies are missing."
    echo "Re-run with one of:"
    echo "  uv run mngr dependencies -i   # interactive install"
    echo "  uv run mngr dependencies -c   # auto-install core deps"
    exit 1
fi

HAS_GEMINI=false
HAS_CLAUDE=false
HAS_AGY=false

if command -v gemini &> /dev/null; then
    HAS_GEMINI=true
fi

if command -v claude &> /dev/null; then
    HAS_CLAUDE=true
fi

if command -v agy &> /dev/null; then
    HAS_AGY=true
fi

if [ "$HAS_GEMINI" = false ] && [ "$HAS_CLAUDE" = false ] && [ "$HAS_AGY" = false ]; then
    echo "Error: None of 'gemini', 'claude', or 'agy' CLIs are installed. At least one is required."
    exit 1
fi

echo "Dependencies met!"
echo " - uv: $(uv --version)"
echo " - npm: $(npm --version)"
if [ "$HAS_GEMINI" = true ]; then
    echo " - gemini: $(gemini --version)"
fi
if [ "$HAS_CLAUDE" = true ]; then
    echo " - claude: $(claude --version)"
fi
if [ "$HAS_AGY" = true ]; then
    echo " - agy: $(agy --version)"
fi
echo ""

echo "======================================"
echo "Installing dependencies..."
echo "======================================"

echo "Running 'git submodule update --init'..."
git submodule update --init

echo "Running 'uv sync'..."
uv sync
echo ""

echo "Running 'npm install' in frontend directory..."
(cd frontend && npm install)
echo ""

echo "Populating template blobs: 'uv run --project \"$(pwd)\" --directory ../templates python download_blobs.py'..."
uv run --project "$(pwd)" --directory ../templates python download_blobs.py
echo ""

echo "======================================"
echo "Starting services..."
echo "======================================"

# Start the backend in the background
echo "Starting backend server (uv run python server.py)..."
uv run python server.py &
BACKEND_PID=$!

# Function to cleanly shut down backend when the script exits
cleanup() {
    echo ""
    echo "Shutting down..."
    echo "Stopping backend (PID: $BACKEND_PID)..."
    kill $BACKEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    echo "Shutdown complete."
}

# Trap EXIT, INT, TERM to run cleanup
trap cleanup EXIT INT TERM

echo "Backend and frontend are starting up..."
echo ""

# Wait briefly to let servers bind their ports, then open browser
(
    sleep 2
    echo "Frontend URL: http://localhost:8939"
    echo "Opening browser..."
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8939 &> /dev/null
    elif command -v open &> /dev/null; then
        open http://localhost:8939 &> /dev/null
    elif command -v python3 &> /dev/null; then
        python3 -m webbrowser http://localhost:8939 &> /dev/null
    fi
) &

# Run the frontend in the foreground
# This takes over the terminal so you can see logs and stop it with Ctrl+C
echo "Starting frontend (npm run dev)..."
cd frontend && npm run dev
