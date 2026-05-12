# AI Scientist (Catalyst)

A tool for autonomous scientific research.

## Architecture

- **Agent Skills:** The main functionality of the AI Scientist is implemented through a set of Agent skills that each perform different steps of the research process.
- **Backend (Python + FastAPI):** Manages the research lifecycle using multi-threading.
- **Agent Layer:** Spawns `gemini` or `claude` CLI processes in headless mode, capturing their JSON outputs and session IDs for traceability.
- **Frontend (React + TypeScript):** A dashboard for starting research tasks, monitoring progress in real-time, and inspecting the data exchange at each step.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) (for Python dependency management)
- [Node.js & npm](https://nodejs.org/) (for the frontend)
- [Gemini CLI](https://github.com/google/gemini-cli) or [Claude Code](https://claude.ai/code) installed and authenticated.

## Getting Started

From the root `src` directory:
```bash
./run.sh
```

The dashboard will be available at `http://localhost:8939`.

## Configuration

The system can be configured using the following environment variables:

- `AI_SCIENTIST_PATH`: The base directory where state and research environments are stored. Defaults to `~/.ai-scientist`.
- `AI_SCIENTIST_MAX_CONCURRENCY_PER_TASK`: The maximum number of concurrent agent steps per task. Defaults to `2`.

## Usage

1. **Start a Task:** Click "NEW TASK" in the dashboard.
2. **Configure:**
   - **Phenomenon:** The scientific topic to investigate.
   - **Framework:** Choose between Gemini CLI or Claude Code.
   - **Model:** Choose a model identifier from the dropdown or enter one manually.
3. **Monitor:** The dashboard polls the backend every 2 seconds to update the timeline.
4. **Inspect:** Click any completed or running step in the timeline to view the raw inputs, JSON outputs, and the **Session ID**.
5. **Recover:** If you want to see the detailed agent logs or manually intervene, use the session ID provided in the inspection panel:
   - For Gemini: `gemini --resume <session_id>`
   - For Claude: `claude --resume <session_id>`

## Data Persistence

- **Tasks State:** The service maintains its state in `tasks_state.json` inside the `AI_SCIENTIST_PATH` (defaults to `~/.ai-scientist/tasks_state.json`). You can stop and restart the backend server without losing track of ongoing or completed research tasks.
- **Research Environments:** Research artifacts and agent workspaces are stored in the `research` subfolder of `AI_SCIENTIST_PATH` (defaults to `~/.ai-scientist/research`). Each task gets its own folder named `task_<short_id>`.


## Troubleshooting

### Claude fails to run bash commands: `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`
If you're on Ubuntu 24.04, follow https://www.jdhodges.com/blog/codex-sandbox-ubuntu-24-04-fix/

### Claude can't enable sandbox
Follow the prerequisites steps from https://code.claude.com/docs/en/sandboxing#prerequisites

### Gemini CLI fails with `When using Gemini API, you must specify the GEMINI_API_KEY environment variable.`
If you've configured Gemini CLI to use API key authentication, it will refuse to run in headless mode unless the GEMINI_API_KEY environment variable is also set.

To resolve this issue, export the GEMINI_API_KEY environment variable before launching the server:
```bash
GEMINI_API_KEY=<your Google AI Studio API key> ./run.sh
```