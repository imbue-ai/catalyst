"""Stage B-Direct smoke test for the direct subprocess-based runners.

Runs `orchestrator.agents.claude.ClaudeAgentRunner` (the
`subprocess.Popen(["claude", "-p", ...])` path that exists in
`framework: "claude"` tasks) against a trivial prompt. Verifies that
restoring the direct code from `origin/main` didn't break it.

Cost: a few cents on Haiku.

Usage (from src/):
    uv run python orchestrator/tests/acceptance/smoke_test_direct_runner.py
"""

import logging
import os
import sys
import tempfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from orchestrator.agents.claude import ClaudeAgentRunner  # noqa: E402

MODEL = "claude-haiku-4-5-20251001"
PROMPT = (
    'Output exactly the JSON `{"hello": "world"}` as your final message '
    "and stop. Do not call any tools."
)


def main() -> int:
    statuses: list[str] = []

    def on_status(s: str) -> None:
        statuses.append(s)
        print(f"  [status] {s[:120]}", flush=True)

    captured_sid: dict[str, str | None] = {"sid": None}

    def on_session_id(sid: str) -> None:
        captured_sid["sid"] = sid
        print(f"  Session ID: {sid}", flush=True)

    runner = ClaudeAgentRunner()
    with tempfile.TemporaryDirectory(prefix="catalyst-direct-smoke-") as env_folder:
        print(f"Running direct smoke task in {env_folder}", flush=True)
        common_env = runner.build_common_environment_variables(
            env_folder=env_folder,
            tx_id="tx_direct_smoke",
        )
        data, session_id, error = runner.run(
            task_id="task_direct_smoke",
            prompt=PROMPT,
            env_folder=env_folder,
            stage="direct-smoke",
            common_environment_variables=common_env,
            model=MODEL,
            on_session_id=on_session_id,
            on_status=on_status,
        )

    print(f"\nResult: data={data!r} session_id={session_id!r} error={error!r}")

    checks = [
        ("got data dict", data == {"hello": "world"}),
        ("no error", error is None),
        ("session_id captured", bool(session_id) and session_id == captured_sid["sid"]),
        # Status callback is optional for direct (stream-json may or may not
        # surface intermediate text), but we still report it.
    ]
    print("\nChecks:")
    all_ok = True
    for label, passed in checks:
        marker = "OK" if passed else "FAIL"
        print(f"  [{marker}] {label}")
        all_ok = all_ok and passed
    print(f"  (info) status callback fired {len(statuses)}x")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
