# AI Scientist (Catalyst)

A tool for autonomous scientific research.

## Documentation

For more detailed information, please see the following guides:

- [Quickstart Guide](docs/quickstart.md): An overview of the system structure and environment templates.
- [Workflows and Add-ons](docs/workflow.md): A reference for all primary workflows and individual add-on steps.
- [CLI Agent Usage](docs/cli.md): Instructions for using AI Scientist skills directly within a CLI agent.

## Architecture

- **Agent Skills:** The main functionality of the AI Scientist is implemented through a set of Agent skills that each perform different steps of the research process.
- **Backend (Python + FastAPI):** Manages the research lifecycle using multi-threading.
- **Agent Layer:** Per step, spawns `gemini` or `claude` either as a direct CLI subprocess (the original implementation) or inside a `mngr`-managed interactive tmux session (the `mngr-claude` / `mngr-gemini` framework variants). Both paths capture JSON outputs for the dashboard; the mngr variants additionally expose each step's session for live attach.
- **Frontend (React + TypeScript):** A dashboard for starting research tasks, monitoring progress in real-time, and inspecting the data exchange at each step.

## Prerequisites

- MacOS, Linux, or WSL2 (Windows)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (for Python dependency management)
- [Node.js & npm](https://nodejs.org/en/download) (for the frontend)
- [Gemini CLI](https://geminicli.com/docs/get-started/installation/) or [Claude Code](https://code.claude.com/docs/en/quickstart#step-1-install-claude-code) installed and authenticated.
- [Claude Code Sandboxing Prerequisites](https://code.claude.com/docs/en/sandboxing#prerequisites) correctly set up when using Claude Code on Linux or WSL

## Getting Started

From the root `src` directory:
```bash
./run.sh
```

The dashboard will be available at `http://localhost:8939`.

## Configuration

The system can be configured using the following environment variables:

- `AI_SCIENTIST_PATH`: The base directory where state and research environments are stored. Defaults to `~/.ai-scientist`.
- `AI_SCIENTIST_MAX_CONCURRENCY_PER_TASK`: The maximum number of concurrent agent steps per task. Defaults to `3`. Some steps (e.g. `review-theory`) will consume more than one unit, as they utilize subagents internally.

## Usage

1. **Start a Task:** Click "NEW TASK" in the dashboard.
2. **Configure:**
   - **Phenomenon:** The scientific topic to investigate.
   - **Framework:** Pick one of four options. `Claude Code` and `Gemini CLI` run the agent CLI directly as a subprocess (the original implementation, suited for `claude --resume <session_id>` recovery). `Claude Code (mngr)` and `Gemini CLI (mngr)` run the same CLIs inside a `mngr`-managed tmux session that you can attach to live via `mngr connect`. The mngr variants require `tmux` and the `imbue-mngr` + `imbue-mngr-claude` Python deps (auto-installed by `uv sync`); the Gemini-mngr variant additionally needs `imbue-mngr-gemini` (not yet on PyPI).
   - **Model:** Choose a model identifier from the dropdown or enter one manually.
3. **Monitor:** The dashboard polls the backend every 2 seconds to update the timeline.
4. **Inspect:** Click any completed or running step in the timeline to view the raw inputs, JSON outputs, and the **Agent Name**.
5. **Recover:** The dashboard's "Inspect Agent" panel shows the right command for the framework. For legacy `claude` / `gemini` tasks it's `cd <env_folder> && claude --resume <session_id>` (or `gemini --resume ...`). For `mngr-claude` / `mngr-gemini` tasks it's `MNGR_HOST_DIR=~/.mngr-ai-scientist mngr connect <session_id>` — attaches a terminal to the agent's tmux session whether it's running or stopped.

## Inspecting past mngr sessions

For tasks created with the `mngr-claude` / `mngr-gemini` frameworks, `mngr` keeps each step's session around after it stops. ai-scientist runs them under a dedicated host_dir at `~/.mngr-ai-scientist/` (separate from your main `~/.mngr/`), so every `mngr` command below needs the `MNGR_HOST_DIR=~/.mngr-ai-scientist` prefix. You can also `export MNGR_HOST_DIR=~/.mngr-ai-scientist` once per shell.

- `MNGR_HOST_DIR=~/.mngr-ai-scientist mngr list --include 'labels["app"] == "ai-scientist"'` lists every mngr-backed agent ai-scientist has ever run.
- `MNGR_HOST_DIR=~/.mngr-ai-scientist mngr transcript <session_id>` prints the recorded turn.
- `MNGR_HOST_DIR=~/.mngr-ai-scientist mngr connect <session_id>` re-attaches to the tmux session (and restarts it if it had stopped).

## Cleanup

Deleting a task from the dashboard removes its env_folder and cancels any running step. For legacy `claude` / `gemini` tasks that's the end of the story (no extra agent state on disk). For `mngr-claude` / `mngr-gemini` tasks, the underlying `mngr` sessions are kept on disk so their transcript and work_dir stay available for debugging. They accumulate over time. To remove every mngr agent associated with a finished task:

```bash
export MNGR_HOST_DIR=~/.mngr-ai-scientist
mngr list --include 'labels["ai-scientist-task"] == "<full_task_id>"' --format '{name}' | mngr destroy --force -
```

The `--format '{name}'` strips the column header that `--fields name` adds (which would break the pipe), and `--force` skips the interactive confirmation prompt so the pipeline runs unattended.

This only removes the agent's `~/.mngr-ai-scientist/agents/` entry; your `~/.ai-scientist/research/task_<id>` artifacts (if still present) are untouched.

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