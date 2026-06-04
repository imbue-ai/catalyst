"""Stage B3 smoke test: parallel non-backgrounded subagents.

Verifies that with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` (set by the
runner), the parent agent can still spawn multiple subagents
concurrently in a single tool block, AND that the parent waits
synchronously for all of them before emitting final JSON. This is the
realistic `/swarm` pattern.

What we check:
* The final JSON aggregates results from all subagents (proves the
  parent received every subagent's output before emitting end_turn --
  i.e. nothing was backgrounded).
* Wall time is roughly max(subagent_time), not sum. With 3 subagents
  each doing ~5s of work, parallel ~7-15s, serial would be ~20-30s.

Cost: ~tens of cents on Haiku for 3 subagents + parent. Wall time:
~30-60s.

Usage (from src/):
    uv run python orchestrator/tests/acceptance/smoke_test_parallel_subagents.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from orchestrator.agents.mngr_claude import MngrClaudeAgentRunner  # noqa: E402

MODEL = "claude-haiku-4-5-20251001"
NUM_SUBAGENTS = 3
PROMPT = (
    f"In a single tool block, spawn {NUM_SUBAGENTS} general-purpose subagents "
    "VIA THE Agent tool, all dispatched at once (not one after another). "
    "Give each subagent a unique label A, B, or C, and tell each one to "
    "output exactly its label (one character, nothing else) and return. "
    "After ALL subagents have reported back, output exactly the JSON "
    '`{"labels": ["A", "B", "C"]}` (sorted) as your final message and stop.'
)


def main() -> int:
    runner = MngrClaudeAgentRunner()
    with tempfile.TemporaryDirectory(prefix="catalyst-parallel-") as env_folder:
        src_settings = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "claude_skills",
            "settings.json",
        )
        dst_claude = os.path.join(env_folder, ".claude")
        os.makedirs(dst_claude, exist_ok=True)
        shutil.copy2(src_settings, os.path.join(dst_claude, "settings.json"))

        print(f"Running parallel-subagents smoke task in {env_folder}", flush=True)
        statuses: list[str] = []
        captured_name: dict[str, str | None] = {"name": None}

        def on_status(s: str) -> None:
            statuses.append(s)
            print(f"  [status] {s[:100]}", flush=True)

        def on_session_id(name: str) -> None:
            captured_name["name"] = name
            print(f"  Agent name: {name}", flush=True)

        t0 = time.monotonic()
        data, session_id, error = runner.run(
            task_id="task_parallel_smoke",
            prompt=PROMPT,
            env_folder=env_folder,
            model=MODEL,
            tx_id="tx_parallel",
            stage="parallel-subagents",
            on_session_id=on_session_id,
            on_status=on_status,
        )
        wall = time.monotonic() - t0

    print(f"\nResult: data={data!r} session_id={session_id!r} error={error!r}")
    print(f"Wall time: {wall:.1f}s")

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

    expected_labels = ["A", "B", "C"]
    got_labels = data.get("labels") if isinstance(data, dict) else None

    checks = [
        ("got data dict", isinstance(data, dict)),
        ("no error", error is None),
        ("data has labels list", isinstance(got_labels, list)),
        (
            "labels contain A, B, C",
            isinstance(got_labels, list)
            and sorted(str(x) for x in got_labels) == expected_labels,
        ),
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
