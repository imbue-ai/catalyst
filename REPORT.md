# Catalyst Setup Report

## What Was Done

Set up and ran the Catalyst AI Scientist repo from scratch on macOS (Darwin 24.6.0).

### Steps Performed

1. **Explored repo structure** — identified it as a Python (FastAPI) backend + React/Vite frontend + git submodules project.
2. **Verified prerequisites** — `uv`, `npm`, `node`, and `claude` CLI all already installed.
3. **Initialized git submodules** — `darwinian_evolver` and `templates` (catalyst-templates) repos cloned.
4. **Installed Python dependencies** — `uv sync` from `src/`. Created venv, installed 110 packages including the local `darwinian-evolver` editable dep.
5. **Installed frontend dependencies** — `npm install` in `src/frontend/`. 342 packages.
6. **Downloaded template blobs** — ran `download_blobs.py` from `templates/` dir, fetched reference papers as PDFs.
7. **Started backend** — `uv run python server.py` (serves on port 8139).
8. **Started frontend** — `npm run dev` in `src/frontend/` (Vite dev server on port 8939, proxies API to 8139).
9. **Migrated to tmux** — both servers moved into named tmux sessions (`catalyst-backend`, `catalyst-frontend`) for persistence.

## Hiccups

- **`uv` `exclude-newer` warning**: The `pyproject.toml` has `exclude-newer = "2 week"` which `uv 0.8.15` can't parse (expects a date, not a relative duration). It printed a warning but proceeded fine by ignoring the lockfile timestamp cutoff. Non-blocking but worth noting — this may be a feature of a newer uv version or a typo in the config.
- **Port confusion**: `run.sh` mentions opening `http://localhost:8939` (the frontend), but the backend actually runs on port 8139. Not a real issue, just needed to check `server.py` to confirm the architecture. The Vite config proxies `/api` to the backend.
- **First backend start** was via `run_in_background` which completed immediately (exit 0) since server.py runs uvicorn in the foreground and it seemingly didn't persist. Restarted with a direct `&` background, then migrated to tmux.

## Recommendations for Next Time

1. **Just run `./run.sh`** — the `run.sh` script handles everything (submodule init, uv sync, npm install, blob download, starting both servers). We did each step manually for visibility, but the script is well-written and self-contained.
2. **tmux from the start** — if you want persistent servers, wrap `run.sh` in tmux or start backend/frontend in separate tmux sessions from the beginning rather than backgrounding with `&`.
3. **Check `uv` version compatibility** — the `exclude-newer = "2 week"` syntax may require a specific uv version. Current uv (0.8.15) works despite the warning.
4. **Existing task state persists** — after restart, the backend picked up a previously completed task from `~/catalyst-research/tasks_state.json`. This is by design (state survives restarts).

## Architecture Summary (for reference)

- Backend: FastAPI + uvicorn on `:8139`, manages research tasks, spawns AI CLI agents
- Frontend: React + Vite on `:8939`, proxies API calls to backend
- Submodules: `darwinian_evolver` (evolution engine), `templates` (research templates with reference papers)
- State: `~/catalyst-research/` (tasks, environments, artifacts)
- Supported agent harnesses: Claude Code, Gemini CLI, Antigravity CLI, Codex CLI (+ mngr variants)
