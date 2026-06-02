"""Stage B2 smoke test: multi-turn / subagent regression coverage.

Reproduces the failure mode that broke `/swarm` and `/explore`: the
parent agent kicks off a subagent via the Agent tool, mngr_claude
transitions the parent to WAITING while the subagent runs, and the
runner needs to keep waiting until the parent emits its FINAL
assistant_message after the subagent returns.

Before the turn_end Stop-hook fix landed, `mngr wait --state WAITING`
returned at the intermediate idle and the runner parsed the wrong
assistant text. The new mechanism (`_wait_for_turn_end` watching for
the Stop-hook-emitted event) waits through the intermediate idle and
returns only after the parent's final assistant_message.

Cost: ~few cents on Haiku (one parent + one trivial subagent).
Wall time: ~30s typical.

Usage (from src/):
    uv run python orchestrator/tests/acceptance/smoke_test_multi_turn.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from orchestrator.agents.mngr_claude import MngrClaudeAgentRunner  # noqa: E402

MODEL = "claude-haiku-4-5-20251001"
PROMPT = (
    "Use the Agent tool to spawn one general-purpose subagent. Tell "
    "the subagent to output exactly the word 'pong' and nothing else, "
    "then return. After the subagent reports back, output exactly the "
    'JSON `{"got_pong": true}` as your final message and stop.'
)


def main() -> int:
    runner = MngrClaudeAgentRunner()
    with tempfile.TemporaryDirectory(prefix="aisci-multiturn-") as env_folder:
        src_settings = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "claude_skills",
            "settings.json",
        )
        dst_claude = os.path.join(env_folder, ".claude")
        os.makedirs(dst_claude, exist_ok=True)
        shutil.copy2(src_settings, os.path.join(dst_claude, "settings.json"))

        print(f"Running multi-turn smoke task in {env_folder}", flush=True)
        captured_name: dict[str, str | None] = {"name": None}
        statuses: list[str] = []

        def on_status(s: str) -> None:
            statuses.append(s)
            print(f"  [status] {s[:100]}", flush=True)

        def on_session_id(name: str) -> None:
            captured_name["name"] = name
            print(
                f"  Agent name: {name}\n"
                f"  Tail transcript:\n"
                f"    MNGR_HOST_DIR=~/.mngr-catalyst mngr transcript {name}",
                flush=True,
            )

        data, session_id, error = runner.run(
            task_id="task_multiturn_smoke",
            prompt=PROMPT,
            env_folder=env_folder,
            model=MODEL,
            tx_id="tx_multiturn",
            stage="multi-turn",
            on_session_id=on_session_id,
            on_status=on_status,
        )

    print(f"\nResult: data={data!r} session_id={session_id!r} error={error!r}")

    name = captured_name["name"] or session_id
    if not name:
        print("FAIL: no agent name was captured")
        return 1

    list_result = subprocess.run(
        ["mngr", "list", "--include", f'name == "{name}"', "--format", "jsonl"],
        check=False,
        capture_output=True,
        text=True,
    )
    state = None
    for line in list_result.stdout.splitlines():
        try:
            d = json.loads(line)
            if d.get("name") == name:
                state = d.get("state")
                break
        except json.JSONDecodeError:
            pass

    checks = [
        ("got data dict", isinstance(data, dict)),
        ("no error", error is None),
        ("data has got_pong: true", isinstance(data, dict) and data.get("got_pong") is True),
        ("at least one status update", len(statuses) > 0),
        ("agent stopped cleanly", state == "STOPPED"),
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
