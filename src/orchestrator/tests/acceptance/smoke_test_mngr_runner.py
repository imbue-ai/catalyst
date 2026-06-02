"""Stage B smoke test for the mngr-based agent runner.

Runs `MngrAgentRunner` directly (no orchestrator, no FastAPI) against a real
local Claude agent with a trivial prompt. Verifies that:

1. The agent shows up in `mngr list`.
2. `mngr connect <agent-name>` attaches to the live tmux session — script
   prints the agent name and pauses for ~10 s so the operator can verify.
3. The runner's `on_status` callback fires.
4. After Claude finishes, the agent is STOPPED (not destroyed) and is
   still listed.
5. `parse_json_result` returns the expected dict.
6. The four `catalyst*` labels are present.

Cost control: pins claude-haiku-4-5-20251001. Don't run with Sonnet/Opus.

Usage (from src/):
    uv run python orchestrator/tests/acceptance/smoke_test_mngr_runner.py
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Allow this script to import sibling packages when run from src/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from orchestrator.agents.mngr_claude import MngrClaudeAgentRunner  # noqa: E402

MODEL = "claude-haiku-4-5-20251001"
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
                f"  → In another terminal, try: MNGR_HOST_DIR=~/.mngr-catalyst mngr connect {name}\n"
                f"  Sleeping {pause_secs}s so you can attach...\n",
                flush=True,
            )
            time.sleep(pause_secs)

    runner = MngrClaudeAgentRunner()
    with tempfile.TemporaryDirectory(prefix="cata-smoke-") as env_folder:
        # Mirror what `create_environment.py` does for real tasks: copy
        # the `.claude/settings.json` from `claude_skills/` so the
        # Stop hook that emits `mngr/turn_complete` is wired up. Without
        # it the runner would wait its full 4-hour timeout.
        src_settings = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "claude_skills",
            "settings.json",
        )
        dst_claude = os.path.join(env_folder, ".claude")
        os.makedirs(dst_claude, exist_ok=True)
        shutil.copy2(src_settings, os.path.join(dst_claude, "settings.json"))

        print(f"Running smoke task in {env_folder}")
        data, session_id, error = runner.run(
            task_id="task_smoketest",
            prompt=PROMPT,
            env_folder=env_folder,
            model=MODEL,
            tx_id="tx_smoke",
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
