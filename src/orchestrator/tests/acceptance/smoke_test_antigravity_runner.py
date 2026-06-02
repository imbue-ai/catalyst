"""Stage B smoke test for the antigravity-based agent runner.

Runs `MngrAntigravityAgentRunner` directly (no orchestrator, no FastAPI)
against a real local Antigravity (`agy`) agent with a trivial prompt.
Verifies that:

1. The agent shows up in `mngr list` (under Catalyst's dedicated
   host_dir).
2. `mngr connect <agent-name>` attaches to the live tmux session — the
   script prints the agent name and pauses for ~10 s so the operator can
   verify.
3. The runner's `on_status` callback fires.
4. After agy finishes, the agent is STOPPED (not destroyed) and is still
   listed.
5. `parse_json_result` returns the expected dict (proving the
   WAITING-state turn-completion strategy fired correctly).

Unlike the Claude smoke test there is no `.claude/settings.local.json` to
provision: the `mngr_antigravity` plugin provisions its own `hooks.json`
(per-agent, under the agent state dir) that maintains the lifecycle
`active` marker, so `mngr wait --state WAITING` is the turn-end signal.
The `[agent_types.antigravity]` settings in `.mngr/settings.toml`
(auto_dismiss_dialogs / auto_allow_permissions) handle the trust dialog and
auto-approval, so a bare temp env_folder is enough.

Requires the `agy` CLI installed and authenticated.

Usage (from src/):
    uv run python orchestrator/tests/acceptance/smoke_test_antigravity_runner.py
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Allow this script to import sibling packages when run from src/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from orchestrator.agents.mngr_antigravity import MngrAntigravityAgentRunner  # noqa: E402

PROMPT = (
    'Output exactly the JSON `{"hello": "world"}` as your final message '
    "and stop. Do not call any tools."
)


def main() -> int:
    statuses: list[str] = []

    def on_status(s: str) -> None:
        statuses.append(s)
        print(f"  [status] {s[:120]}")

    captured_name: dict[str, str | None] = {"name": None}

    pause_secs = int(os.environ.get("AISCI_SMOKE_PAUSE_SECONDS", "10"))

    def on_session_id(name: str) -> None:
        captured_name["name"] = name
        print(f"\n  Agent name: {name}", flush=True)
        if pause_secs > 0:
            print(
                f"  -> In another terminal, try: MNGR_HOST_DIR=~/.mngr-catalyst mngr connect {name}\n"
                f"  Sleeping {pause_secs}s so you can attach...\n",
                flush=True,
            )
            time.sleep(pause_secs)

    runner = MngrAntigravityAgentRunner()
    with tempfile.TemporaryDirectory(prefix="cata-ag-smoke-") as env_folder:
        print(f"Running smoke task in {env_folder}")
        data, session_id, error = runner.run(
            task_id="task_agsmoketest",
            prompt=PROMPT,
            env_folder=env_folder,
            model=None,
            tx_id="tx_ag_smoke",
            stage="smoke",
            on_session_id=on_session_id,
            on_status=on_status,
        )

    print(f"\nResult: data={data!r} session_id={session_id!r} error={error!r}")

    name = captured_name["name"] or session_id
    if not name:
        print("FAIL: no agent name was captured")
        return 1

    list_result = subprocess.run(
        ["mngr", "list", "--include", 'labels["app"] == "catalyst"', "--format", "jsonl"],
        check=False,
        capture_output=True,
        text=True,
    )
    list_names = []
    for line in list_result.stdout.splitlines():
        try:
            list_names.append(json.loads(line).get("name"))
        except json.JSONDecodeError:
            pass

    checks = [
        ("got data dict", data == {"hello": "world"}),
        ("no error", error is None),
        ("at least one status update", len(statuses) > 0),
        ("agent visible after stop", name in list_names),
    ]
    print("\nChecks:")
    all_ok = True
    for label, passed in checks:
        marker = "OK" if passed else "FAIL"
        print(f"  [{marker}] {label}")
        all_ok = all_ok and passed

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
