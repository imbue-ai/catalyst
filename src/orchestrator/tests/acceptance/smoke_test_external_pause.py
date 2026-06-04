"""Stage B-Pause smoke test: external `mngr stop` interrupts the runner.

Reproduces the dashboard's pause behavior: while the runner is in
`_wait_for_turn_end` (parent agent mid-turn, no Stop hook fired yet),
something external calls `mngr stop <agent>` -- which is exactly what
`cancel_task_process` does when the user clicks Pause. The runner
should exit promptly, NOT block for the full 6-hour wait deadline.

How: spawn a thread that sleeps ~10s after the agent name is captured,
then issues `mngr stop`. The main thread's `runner.run()` should return
within seconds of that, with `saw_turn_end == False` (the agent never
emitted turn_end, it was killed). Wall time should be roughly the
duration of the agent's first work + 10s pause delay + a few seconds
of teardown -- much less than `_WAIT_TIMEOUT_SECONDS`.

Cost: a few cents on Haiku (one parent + the early-stopped subagent
work). Wall time: ~20-30s.

Usage (from src/):
    uv run python orchestrator/tests/acceptance/smoke_test_external_pause.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from orchestrator.agents.mngr_claude import MngrClaudeAgentRunner  # noqa: E402
from orchestrator.agents.mngr_runner import _WAIT_TIMEOUT_SECONDS  # noqa: E402
from orchestrator.utils import mngr_env  # noqa: E402

MODEL = "claude-haiku-4-5-20251001"
# A prompt that takes a while -- spawn 3 subagents that each report a
# moderately-sized analysis -- so the runner is still in
# `_wait_for_turn_end` when we externally stop it.
PROMPT = (
    "Use the Agent tool to spawn 3 general-purpose subagents in parallel. "
    "Tell each one to compose a paragraph (~100 words) explaining a "
    "different aspect of why 2+2=4. After all three report back, output "
    'a JSON object `{"summary": "..."}` summarizing them. '
    "This entire flow should take at least 20 seconds."
)
PAUSE_DELAY_S = 10.0


def main() -> int:
    runner = MngrClaudeAgentRunner()
    with tempfile.TemporaryDirectory(prefix="catalyst-pause-") as env_folder:
        src_settings = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "claude_skills",
            "settings.json",
        )
        dst_claude = os.path.join(env_folder, ".claude")
        os.makedirs(dst_claude, exist_ok=True)
        shutil.copy2(src_settings, os.path.join(dst_claude, "settings.json"))

        print(f"Running external-pause smoke task in {env_folder}", flush=True)
        captured_name: dict[str, str | None] = {"name": None}
        statuses: list[str] = []

        def on_status(s: str) -> None:
            statuses.append(s)
            print(f"  [status] {s[:100]}", flush=True)

        def on_session_id(name: str) -> None:
            captured_name["name"] = name
            print(f"  Agent name: {name}", flush=True)
            print(
                f"  Scheduling external `mngr stop` in {PAUSE_DELAY_S:.0f}s "
                "(simulates dashboard Pause click)...",
                flush=True,
            )

            def stop_after_delay():
                time.sleep(PAUSE_DELAY_S)
                print("  >>> External stop firing now <<<", flush=True)
                subprocess.run(
                    ["mngr", "stop", name],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=mngr_env(),
                )

            threading.Thread(target=stop_after_delay, daemon=True).start()

        t0 = time.monotonic()
        data, session_id, error = runner.run(
            task_id="task_pause_smoke",
            prompt=PROMPT,
            env_folder=env_folder,
            model=MODEL,
            tx_id="tx_pause",
            stage="pause-smoke",
            on_session_id=on_session_id,
            on_status=on_status,
        )
        wall = time.monotonic() - t0

    print(f"\nResult: data={data!r} session_id={session_id!r} error={error!r}")
    print(f"Wall time: {wall:.1f}s")

    # Acceptance: runner returned within ~30s of the stop firing,
    # NOT 6 hours later. `wall` is the runner's wall time, so the
    # floor is "cannot exit before the external stop fires" and the
    # ceiling is "must exit shortly after the external stop fires".
    WALL_TIME_FLOOR = PAUSE_DELAY_S  # rough lower bound
    WALL_TIME_CEILING = PAUSE_DELAY_S + 60.0  # generous upper bound

    checks = [
        ("runner returned an error and no data after external stop", error is not None and data is None),
        (
            f"runner exited within {WALL_TIME_CEILING:.0f}s of start "
            f"(not the {_WAIT_TIMEOUT_SECONDS}s wait deadline)",
            WALL_TIME_FLOOR <= wall <= WALL_TIME_CEILING,
        ),
        ("session_id was captured", bool(session_id)),
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
