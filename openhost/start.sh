#!/bin/bash

# Exit immediately if any command fails
set -e

# Port configuration
export CATALYST_PORT=8141
export ADMIN_PORT=8139

# Ensure we have a clean environment variables for Catalyst
export CATALYST_HOST=0.0.0.0
export CATALYST_PATH=$OPENHOST_APP_DATA_DIR/imbue-catalyst

echo "=== OpenHost Gateway Startup Shell ==="

# PID of background Catalyst server
CATALYST_PID=""

# Cleanup handler on exit or signals
cleanup() {
    echo "Shutting down servers cleanly..."
    if [ -n "$CATALYST_PID" ]; then
        echo "Killing Catalyst server (PID: $CATALYST_PID)..."
        kill -TERM "$CATALYST_PID" 2>/dev/null || true
        wait "$CATALYST_PID" 2>/dev/null || true
    fi
    echo "Done. Exiting."
}

# Catch SIGINT, SIGTERM, and EXIT
trap cleanup EXIT INT TERM

# 1. Start main Catalyst server on internal port 8141
echo "Starting Catalyst server on port $CATALYST_PORT..."
cd /app/src
# Run using uv within the correct directory
uv run python server.py &
CATALYST_PID=$!

echo "Catalyst server started with PID $CATALYST_PID"

# Wait a brief moment to ensure Catalyst has had a chance to start binding
sleep 2

# 2. Start OpenHost admin proxy gateway server on public port 8139
echo "Starting OpenHost Admin/Proxy gateway on port $ADMIN_PORT..."
cd /app/src
uv run python ../openhost/openhost_server.py
