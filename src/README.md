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
- **Agent Layer:** Per step, spawns `claude` as a direct CLI subprocess (the original implementation), or runs `claude` / `agy` (the Antigravity CLI) inside a `mngr`-managed interactive tmux session (the `mngr-claude` / `mngr-antigravity` framework variants). Both paths capture JSON outputs for the dashboard; the mngr variants additionally expose each step's session for live attach.
- **Frontend (React + TypeScript):** A dashboard for starting research tasks, monitoring progress in real-time, and inspecting the data exchange at each step.

## Prerequisites

- MacOS, Linux, or WSL2 (Windows)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (for Python dependency management)
- [Node.js & npm](https://nodejs.org/en/download) (for the frontend)
- [Antigravity CLI](https://antigravity.google/docs/cli-overview) (`agy`) or [Claude Code](https://code.claude.com/docs/en/quickstart#step-1-install-claude-code) installed and authenticated.
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
   - **Framework:** `Claude Code` runs the `claude` CLI directly as a subprocess. `Claude Code (mngr)` / `Antigravity CLI (mngr)` run their CLI (`claude` / `agy`) inside a `mngr`-managed tmux session you can attach to live via `mngr connect`. The Antigravity variant needs `imbue-mngr-antigravity` and the `agy` binary on PATH.
   - **Model:** Choose a model identifier from the dropdown or enter one manually.
3. **Monitor:** The dashboard polls the backend every 2 seconds to update the timeline.
4. **Inspect:** Click any completed or running step in the timeline to view the raw inputs, JSON outputs, and the **Agent Name**.
5. **Recover:** The dashboard's "Inspect Agent" panel shows the right command for the framework. For legacy `claude` tasks it's `cd <env_folder> && claude --resume <session_id>`. For `mngr-claude` / `mngr-antigravity` tasks it's `MNGR_HOST_DIR=~/.mngr-ai-scientist mngr connect <session_id>` — attaches a terminal to the agent's tmux session whether it's running or stopped.

## Inspecting past mngr sessions

For tasks created with the `mngr-claude` / `mngr-antigravity` frameworks, `mngr` keeps each step's session around after it stops. ai-scientist runs them under a dedicated host_dir at `~/.mngr-ai-scientist/` (separate from your main `~/.mngr/`), so every `mngr` command below needs the `MNGR_HOST_DIR=~/.mngr-ai-scientist` prefix. You can also `export MNGR_HOST_DIR=~/.mngr-ai-scientist` once per shell.

- `MNGR_HOST_DIR=~/.mngr-ai-scientist mngr list --include 'labels["app"] == "ai-scientist"'` lists ai-scientist's mngr-backed agents that haven't been destroyed yet.
- `MNGR_HOST_DIR=~/.mngr-ai-scientist mngr transcript <session_id>` prints the recorded turn.
- `MNGR_HOST_DIR=~/.mngr-ai-scientist mngr connect <session_id>` re-attaches to the tmux session (and restarts it if it had stopped).

## Cleanup

Deleting a task from the dashboard removes its env_folder and cancels any running step. **Per-session state outside the env_folder is preserved** in all three framework cases — this is intentional so transcripts remain inspectable after a task is gone, and it matches the underlying CLI's own behavior:

- Legacy `claude` leaves its session JSONLs under `~/.claude/projects/<sanitized-env-folder>/<session_id>.jsonl`. The CLI doesn't clean these up on its own.
- `mngr-claude` / `mngr-antigravity` leave the agent's transcript + work_dir under `~/.mngr-ai-scientist/agents/<agent-id>/` (mngr keeps the per-agent state even after `mngr destroy`). The Antigravity CLI additionally keeps its own per-conversation logs under `~/.gemini/antigravity-cli/`, the same way the legacy claude CLI keeps `~/.claude` session files.

To remove every mngr agent associated with a finished task:

```bash
export MNGR_HOST_DIR=~/.mngr-ai-scientist
mngr list --include 'labels["ai-scientist-task"] == "<full_task_id>"' --format '{name}' | mngr destroy --force -
```

The `--format '{name}'` strips the column header that `--fields name` adds (which would break the pipe), and `--force` skips the interactive confirmation prompt so the pipeline runs unattended.

## Data Persistence

- **Tasks State:** The service maintains its state in `tasks_state.json` inside the `AI_SCIENTIST_PATH` (defaults to `~/.ai-scientist/tasks_state.json`). You can stop and restart the backend server without losing track of ongoing or completed research tasks.
- **Research Environments:** Research artifacts and agent workspaces are stored in the `research` subfolder of `AI_SCIENTIST_PATH` (defaults to `~/.ai-scientist/research`). Each task gets its own folder named `task_<short_id>`.


## Troubleshooting

### Claude fails to run bash commands: `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`
If you're on Ubuntu 24.04, follow https://www.jdhodges.com/blog/codex-sandbox-ubuntu-24-04-fix/

### Claude can't enable sandbox
Follow the prerequisites steps from https://code.claude.com/docs/en/sandboxing#prerequisites

### Antigravity (`agy`) is not signed in
The `mngr-antigravity` framework drives the Antigravity CLI in a headless tmux session, so it can't complete an interactive OAuth sign-in. Authenticate `agy` once in a normal terminal (run `agy`, follow the sign-in prompt) before starting antigravity tasks. mngr reuses the credentials it writes under `~/.gemini/antigravity-cli/`.

### Antigravity (`agy`) is shadowed by the desktop app
If the Antigravity desktop app is installed, its bundled `agy` shim can shadow the standalone CLI on `PATH`. Confirm `which agy` points at the standalone Go binary (e.g. `~/.local/bin/agy`); if not, remove the desktop app's `bin/agy` or set an absolute `command` path on the `antigravity` agent type in your mngr config.