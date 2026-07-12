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

HAS_GEMINI=false
HAS_CLAUDE=false
HAS_AGY=false
HAS_CODEX=false

if command -v gemini &> /dev/null; then
    HAS_GEMINI=true
fi

if command -v claude &> /dev/null; then
    HAS_CLAUDE=true
fi

if command -v agy &> /dev/null; then
    HAS_AGY=true
fi

if command -v codex &> /dev/null; then
    HAS_CODEX=true
fi

if [ "$HAS_GEMINI" = false ] && [ "$HAS_CLAUDE" = false ] && [ "$HAS_AGY" = false ] && [ "$HAS_CODEX" = false ]; then
    echo "Error: None of 'gemini', 'claude', 'agy', or 'codex' CLIs are installed. At least one is required."
    exit 1
fi

echo "Dependencies met!"
echo " - uv: $(uv --version)"
echo " - npm: $(npm --version)"
if [ "$HAS_GEMINI" = true ]; then
    echo " - gemini"
fi
if [ "$HAS_CLAUDE" = true ]; then
    echo " - claude"
fi
if [ "$HAS_AGY" = true ]; then
    echo " - agy"
fi
if [ "$HAS_CODEX" = true ]; then
    echo " - codex"
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
(cd frontend && npm install --no-audit --no-fund)
echo ""

echo "Running 'npm run build' to build the frontend..."
(cd frontend && npm run build)
echo ""

echo "Populating template blobs: 'uv run --project \"$(pwd)\" --directory ../templates python download_blobs.py'..."
uv run --project "$(pwd)" --directory ../templates python download_blobs.py
echo ""

echo "======================================"
echo "Starting services..."
echo "======================================"

# Wait briefly to let backend bind its port, then open browser
(
    sleep 2
    PORT=${CATALYST_PORT:-8139}
    echo "Application URL: http://localhost:${PORT}"
    echo "Opening browser..."
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:${PORT} &> /dev/null
    elif command -v open &> /dev/null; then
        open http://localhost:${PORT} &> /dev/null
    elif command -v python3 &> /dev/null; then
        python3 -m webbrowser http://localhost:${PORT} &> /dev/null
    fi
) &

# Run the backend in the foreground
echo "Starting backend server (uv run python server.py)..."
uv run python server.py

