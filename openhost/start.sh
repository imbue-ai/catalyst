#!/bin/bash

# Exit immediately if any command fails
set -e

# Port configuration
export CATALYST_PORT=8141
export ADMIN_PORT=8139

# Configure Catalyst environment variables
export CATALYST_HOST=0.0.0.0
export CATALYST_PATH=$OPENHOST_APP_DATA_DIR
export CATALYST_DISABLE_SANDBOXING=1  # Sandboxing is currently incompatible with OpenHost VMs, but also less necessary.

echo "=== OpenHost Gateway Startup Shell ==="

# Start OpenHost admin proxy gateway server on public port 8139
echo "Starting OpenHost Admin/Proxy gateway on port $ADMIN_PORT..."
cd /app/src
exec uv run python ../openhost/openhost_server.py
