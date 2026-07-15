# Stage 1: Build the main frontend static files
FROM docker.io/library/node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY src/frontend/package*.json ./
RUN npm install
COPY src/frontend/ ./
RUN npm run build

# Stage 2: Build the openhost admin frontend
FROM docker.io/library/node:20-slim AS admin-frontend-builder
WORKDIR /app/admin-frontend
COPY openhost/frontend/package*.json ./
RUN npm install
COPY openhost/frontend/ ./
RUN npm run build

# Stage 3: Final runtime image
FROM docker.io/library/python:3.12-slim
WORKDIR /app

# Install system dependencies, curl, and Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 from NodeSource (required for Gemini CLI and other node integrations)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Install common agent CLIs (Claude Code, Antigravity CLI, Codex CLI, and Gemini CLI)
RUN printf '#!/bin/sh\nexec "$@"\n' > /usr/local/bin/sudo && chmod +x /usr/local/bin/sudo \
    && curl -fsSL https://claude.ai/install.sh | bash \
    && curl -fsSL https://antigravity.google/cli/install.sh | bash \
    && curl -fsSL https://chatgpt.com/codex/install.sh | sh \
    && npm install -g @google/gemini-cli \
    && rm -f /usr/local/bin/sudo

# Copy python packaging files for better caching
COPY src/pyproject.toml src/uv.lock ./src/
COPY darwinian_evolver /app/darwinian_evolver

# Sync dependencies using uv
WORKDIR /app/src
RUN uv sync --frozen --no-install-project

# Copy the rest of the source directories
COPY src/ /app/src
RUN uv sync --frozen
COPY templates /app/templates

# Pre-download large template reference blobs during image build to optimize startup time
WORKDIR /app/templates
RUN python3 download_blobs.py

# Copy the pre-built main frontend files into the correct backend location to serve them
COPY --from=frontend-builder /app/frontend/dist /app/src/frontend/dist

# Copy the openhost python server and start script
COPY openhost/ /app/openhost
# Copy the pre-built openhost admin frontend
COPY --from=admin-frontend-builder /app/admin-frontend/dist /app/openhost/frontend/dist

# Expose backend gateway port
EXPOSE 8139

# Configure environment variables for OpenHost runtime
ENV CATALYST_PORT=8141

WORKDIR /app
RUN chmod +x /app/openhost/start.sh
CMD ["/app/openhost/start.sh"]
