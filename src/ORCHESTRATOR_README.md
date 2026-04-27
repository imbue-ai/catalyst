# AI Scientist Orchestrator

A dedicated orchestration service and dashboard for autonomous scientific research. This system replaces the unreliable agent-sequenced `develop-theory` loop with a robust Python-based state machine that coordinates multi-step research tasks.

## Architecture

- **Backend (Python + FastAPI):** Manages the research lifecycle (Literature Review -> Explore -> Write Theory -> Review & Refinement) using multi-threading.
- **Agent Layer:** Spawns `gemini` or `claude` CLI processes in headless mode, capturing their JSON outputs and session IDs for traceability.
- **Frontend (React + TypeScript):** A modern, minimalist dashboard for starting tasks, monitoring progress in real-time, and inspecting the data exchange at each step.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) (for Python dependency management)
- [Node.js & npm](https://nodejs.org/) (for the frontend)
- [Gemini CLI](https://github.com/google/gemini-cli) or [Claude Code](https://claude.ai/code) installed and authenticated.

## Getting Started

### 1. Install Backend Dependencies

From the root `src` directory:

```bash
uv sync
```

### 2. Start the Backend Server

```bash
uv run python server.py
```
The backend runs on `http://localhost:8000`.

### 3. Start the Frontend

In a new terminal, navigate to the `frontend` folder:

```bash
cd frontend
npm install
npm run dev
```
The dashboard will be available at `http://localhost:5173`.

## Usage

1. **Start a Task:** Click "NEW TASK" in the dashboard.
2. **Configure:**
   - **Phenomenon:** The scientific topic to investigate.
   - **Environment Folder:** A local directory where the research will happen (e.g., `../bifurcation_gym`).
   - **Framework:** Choose between Gemini CLI or Claude Code.
3. **Monitor:** The dashboard polls the backend every 5 seconds to update the timeline.
4. **Inspect:** Click any completed or running step in the timeline to view the raw inputs, JSON outputs, and the **Session ID**.
5. **Recover:** If you want to see the detailed agent logs or manually intervene, use the session ID provided in the inspection panel:
   - For Gemini: `gemini --resume <session_id>`
   - For Claude: `claude --resume <session_id>`

## Persistence

The service maintains its state in `tasks_state.json`. You can stop and restart the backend server without losing track of ongoing or completed research tasks.
