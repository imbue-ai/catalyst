"""Stage B4 smoke test: the /swarm skill cascade must not stop early.

This is the regression guard for the failure mode where the runner harvests
the parent's *pre-subagent preamble* ("I'll spawn N agents...") instead of
its final, post-completion message. It exercises the real skill cascade
(`/swarm` fans out N parallel subagents, each with a distinct approach, then
collects all results into a "## Swarm Results" report) rather than a
hand-written "Agent tool" prompt -- the cascade is what surfaced the bug in
practice, because the parent sits idle while N substantial subagents run.

Unlike the other subagent smokes, this installs the FULL `claude_skills` tree
into the agent's `.claude/` (the way `create_environment.py` maps
`claude_skills -> .claude` for real tasks), so the `/swarm` skill actually
exists in the agent.

`/swarm` emits a markdown report, not JSON, so the runner returns it as a
parse-failure whose error carries a preview of the harvested final text. The
check is on that harvested text:
  - contains the "## Swarm Results" report with multiple "### Agent N"
    sections -> the runner waited for the whole cascade (PASS).
  - is just the "I'll spawn ..." preamble -> the runner stopped early (FAIL).

Cost: ~tens of cents on Haiku (one parent + N trivial subagents). Wall time:
~40-60s.

Usage (from src/):
    uv run python orchestrator/tests/acceptance/smoke_test_swarm_cascade.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
)

from orchestrator.agents.mngr_claude import MngrClaudeAgentRunner  # noqa: E402
from orchestrator.agents.mngr_runner import mngr_env  # noqa: E402

MODEL = "claude-haiku-4-5-20251001"
NUM_AGENTS = 5
PROMPT = (
    f'/swarm "Write exactly one short paragraph explaining why 2+2=4." N={NUM_AGENTS}'
)


def _harvested_text(data, error: str | None) -> str:
    """Recover the final assistant text the runner harvested.

    `/swarm` returns markdown, so the runner reports a JSON parse failure
    whose message embeds `Preview: <harvested text>` (truncated). If a
    future skill output does parse as JSON, fall back to the serialized
    dict. This is what the *runner* saw, so it is the authoritative signal
    for the early-stop regression -- but it is truncated, so the full
    report is read separately via `_full_final_assistant_text`.
    """
    if isinstance(data, dict):
        return json.dumps(data)
    if error and "Preview:" in error:
        return error.split("Preview:", 1)[1]
    return error or ""


def _full_final_assistant_text(agent_name: str) -> str:
    """Read the agent's untruncated final assistant message from the common
    transcript (the same source the runner harvests), so completion checks
    can inspect the whole `/swarm` report rather than the runner's 800-char
    error preview."""
    result = subprocess.run(
        [
            "mngr",
            "event",
            agent_name,
            "--source",
            "claude/common_transcript",
            "--format",
            "jsonl",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=mngr_env(),
    )
    last_text = ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "assistant_message":
            text = event.get("text")
            if isinstance(text, str) and text:
                last_text = text
    return last_text


def main() -> int:
    runner = MngrClaudeAgentRunner()
    statuses: list[str] = []
    captured_name: dict[str, str | None] = {"name": None}

    def on_status(s: str) -> None:
        statuses.append(s)
        print(f"  [status] {s[:90]}", flush=True)

    def on_session_id(name: str) -> None:
        captured_name["name"] = name
        print(f"  Agent name: {name}", flush=True)

    with tempfile.TemporaryDirectory(prefix="catalyst-swarm-") as env_folder:
        # Install the full claude_skills tree (settings.json + skills/) the
        # way create_environment.py does, so the `/swarm` skill exists.
        src_claude_skills = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            ),
            "claude_skills",
        )
        shutil.copytree(src_claude_skills, os.path.join(env_folder, ".claude"))

        print(f"Running /swarm cascade smoke in {env_folder}", flush=True)
        common_env = runner.build_common_environment_variables(
            env_folder=env_folder,
            tx_id="tx_swarm",
        )
        data, session_id, error = runner.run(
            task_id="task_swarm_smoke",
            prompt=PROMPT,
            env_folder=env_folder,
            stage="swarm-cascade",
            common_environment_variables=common_env,
            model=MODEL,
            on_session_id=on_session_id,
            on_status=on_status,
        )

    print(f"\nResult: data={data!r} session_id={session_id!r}")
    print(f"Error (carries harvested preview): {error!r}")

    name = captured_name["name"] or session_id
    if not name:
        print("FAIL: no agent name was captured")
        return 1

    list_result = subprocess.run(
        ["mngr", "list", "--include", f'name == "{name}"', "--format", "jsonl"],
        check=False,
        capture_output=True,
        text=True,
        env=mngr_env(),
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

    # What the RUNNER harvested (truncated): the authoritative signal for the
    # early-stop regression -- it must be the collected report, not the
    # pre-dispatch preamble.
    harvested = _harvested_text(data, error)
    harvested_lower = harvested.lower()
    looks_like_preamble = bool(
        re.match(r"\s*(i'll|i will|let me|i'm going to)\b", harvested_lower)
    ) and "swarm results" not in harvested_lower

    # The full (untruncated) final message, for a strong completion check that
    # all N subagents' sections made it into the report.
    full_final = _full_final_assistant_text(name)
    agent_sections = len(re.findall(r"###\s*agent\s*\d", full_final.lower()))

    checks = [
        ("at least one status update", len(statuses) > 0),
        ("agent stopped cleanly", state == "STOPPED"),
        (
            "runner harvested the swarm report, not the preamble",
            "swarm results" in harvested_lower and not looks_like_preamble,
        ),
        (
            f"final report aggregates all {NUM_AGENTS} agents (got {agent_sections})",
            agent_sections >= NUM_AGENTS,
        ),
    ]
    print("\nChecks:")
    all_ok = True
    for label, passed in checks:
        marker = "OK" if passed else "FAIL"
        print(f"  [{marker}] {label}")
        all_ok = all_ok and passed

    if not all_ok:
        print(f"\nHarvested final text (first 600 chars):\n{harvested[:600]}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
