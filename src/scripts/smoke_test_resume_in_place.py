"""Stage B-Resume smoke test for `MngrAgentRunner.resume_in_place`.

End-to-end exercise of the resume-after-pause path:

1. Start a multi-subagent task (long enough that we can interrupt it).
2. Wait until the parent agent has produced some visible work but
   before it would finish on its own, then externally `mngr stop`
   the agent. This simulates the user clicking Pause in the dashboard
   while the step was still running.
3. The first `runner.run(...)` call returns with an error (the pause-fix
   makes it exit promptly on external stop rather than waiting the
   full deadline).
4. Call `runner.resume_in_place(agent_name=<captured session_id>, ...)`
   to pick up. The runner should `mngr start` the existing agent,
   `mngr message --message-file <"Continue where you left off.">`, and
   then wait for the resumed turn's `turn_end`.

Verifies:
* The resumed run returns the SAME `session_id` (proves the agent was
  reused rather than a fresh one created).
* The resumed run's final JSON parses successfully (proves the agent's
  prior conversation context survived the pause and the "Continue"
  nudge produced a real completion).
* The agent is STOPPED at the end (normal post-run state).

Cost: a few cents on Haiku (~2 short turns plus a brief subagent fan-out).
Wall time: ~60-90s typical.

Usage (from src/):
    uv run python scripts/smoke_test_resume_in_place.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.agents.mngr_claude import MngrClaudeAgentRunner  # noqa: E402

MODEL = "claude-haiku-4-5-20251001"
INITIAL_PROMPT = (
    "Use the Agent tool to spawn 2 general-purpose subagents in a single "
    "tool block. Tell each subagent to count slowly from 1 to 5 (one number "
    "per second, no other output) and return the count. After BOTH subagents "
    "report back, output exactly the JSON "
    '`{"counts": [5, 5]}` as your final message and stop.'
)
STOP_AFTER_SECS = 12.0


def _seed_settings(env_folder: str) -> None:
    src_settings = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "claude_skills",
        "settings.local.json",
    )
    dst_claude = os.path.join(env_folder, ".claude")
    os.makedirs(dst_claude, exist_ok=True)
    shutil.copy2(src_settings, os.path.join(dst_claude, "settings.local.json"))


def _schedule_external_stop(captured_name: dict, delay: float) -> threading.Thread:
    def stop_after_delay() -> None:
        time.sleep(delay)
        name = captured_name.get("name")
        if not name:
            print(f"  (external stopper: no agent name after {delay}s; giving up)", flush=True)
            return
        print(f"  >>> External `mngr stop {name}` firing now <<<", flush=True)
        subprocess.run(
            ["mngr", "stop", name],
            check=False,
            capture_output=True,
            text=True,
        )

    t = threading.Thread(target=stop_after_delay, daemon=True)
    t.start()
    return t


def _agent_state(name: str) -> str | None:
    result = subprocess.run(
        ["mngr", "list", "--include", f'name == "{name}"', "--format", "jsonl"],
        check=False,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        try:
            d = json.loads(line)
            if d.get("name") == name:
                return d.get("state")
        except json.JSONDecodeError:
            pass
    return None


def main() -> int:
    runner = MngrClaudeAgentRunner()
    with tempfile.TemporaryDirectory(prefix="aisci-resume-") as env_folder:
        _seed_settings(env_folder)

        print(f"Running resume-in-place smoke task in {env_folder}", flush=True)
        captured_name: dict[str, str | None] = {"name": None}
        statuses: list[str] = []

        def on_status(s: str) -> None:
            statuses.append(s)
            print(f"  [status] {s[:100]}", flush=True)

        def on_session_id(name: str) -> None:
            # Called by both run() and resume_in_place(); just record + log.
            captured_name["name"] = name
            print(f"  Agent name: {name}", flush=True)

        # ---- First leg: spawn, get paused externally, runner returns ----
        print(
            f"  Scheduling external `mngr stop` in {STOP_AFTER_SECS:.0f}s "
            "(simulates dashboard Pause click)...",
            flush=True,
        )
        _schedule_external_stop(captured_name, STOP_AFTER_SECS)
        t0 = time.monotonic()
        first_data, first_sid, first_err = runner.run(
            task_id="task_resume_smoke",
            prompt=INITIAL_PROMPT,
            env_folder=env_folder,
            model=MODEL,
            tx_id="tx_resume_smoke",
            stage="resume-smoke",
            on_session_id=on_session_id,
            on_status=on_status,
        )
        first_wall = time.monotonic() - t0

        print(
            f"\nFirst leg: data={first_data!r} session_id={first_sid!r} "
            f"error={(first_err[:120] if first_err else None)!r}",
            flush=True,
        )
        print(f"First leg wall time: {first_wall:.1f}s", flush=True)

        # Brief pause so the dashboard's "agent visible after stop"
        # contract holds (matches what the orchestrator's pause flow
        # looks like in production).
        time.sleep(2.0)

        # ---- Second leg: resume the same agent in place ----
        print(
            f"\nCalling resume_in_place against {first_sid}...",
            flush=True,
        )
        t1 = time.monotonic()
        resume_data, resume_sid, resume_err = runner.resume_in_place(
            task_id="task_resume_smoke",
            agent_name=first_sid,
            env_folder=env_folder,
            model=MODEL,
            tx_id="tx_resume_smoke",
            stage="resume-smoke",
            on_session_id=on_session_id,
            on_status=on_status,
        )
        resume_wall = time.monotonic() - t1

    print(
        f"\nResume leg: data={resume_data!r} session_id={resume_sid!r} "
        f"error={(resume_err[:120] if resume_err else None)!r}",
        flush=True,
    )
    print(f"Resume leg wall time: {resume_wall:.1f}s", flush=True)

    final_state = _agent_state(first_sid) if first_sid else None

    checks = [
        ("first leg returned promptly (within 70s, not the 4h wait)", first_wall < 70.0),
        ("first leg captured a session_id", bool(first_sid)),
        (
            "resume returned same session_id (agent was reused, not recreated)",
            bool(resume_sid) and resume_sid == first_sid,
        ),
        ("resume produced parseable JSON output", isinstance(resume_data, dict)),
        ("resume had no error", resume_err is None),
        ("agent ended STOPPED", final_state == "STOPPED"),
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
