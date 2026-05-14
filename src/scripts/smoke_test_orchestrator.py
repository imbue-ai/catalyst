"""Stage C smoke test for the orchestrator + agent runner end-to-end.

Posts a single-step `_smoke` workflow task to a running backend and waits
for it to complete. Verifies that:

1. The dashboard would see live status updates (we read the backend's
   /api/tasks polling endpoint, same as the React frontend does).
2. The mngr agent for the step has the expected `app=ai-scientist` and
   `ai-scientist-task=<id>` labels.
3. On success, `Step.session_id` is set and the agent is STOPPED.
4. The /smoke skill ran end-to-end (the recorded JSON output contains
   `skill_ran: true`), proving home-settings + skill resolution work
   inside the mngr-managed tmux session.

Cost control: pins claude-haiku-4-5-20251001.

Usage (from src/, after starting the backend separately):
    AI_SCIENTIST_PATH=/tmp/aisci-smoke-c uv run python scripts/smoke_test_orchestrator.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

# Pick up the same isolated MNGR_HOST_DIR default the backend uses, so
# our `mngr list` lookup finds the agent the runner just created.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator import utils  # noqa: E402, F401

BACKEND_URL = os.environ.get("AISCI_BACKEND_URL", "http://localhost:8939")
MODEL = "claude-haiku-4-5-20251001"
TIMEOUT_SECONDS = 300


def _http_post(path, body):
    req = urllib.request.Request(
        BACKEND_URL + path,
        method="POST",
    )
    if isinstance(body, dict):
        # The /api/tasks endpoint expects a multipart form with a `request`
        # JSON field, mirroring the React frontend.
        boundary = "----aisci-smoke-boundary"
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        body_bytes = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="request"\r\n\r\n'
            f"{json.dumps(body)}\r\n"
            f"--{boundary}--\r\n"
        ).encode()
    else:
        body_bytes = body
    with urllib.request.urlopen(req, body_bytes, timeout=30) as resp:
        return json.loads(resp.read())


def _http_get(path):
    with urllib.request.urlopen(BACKEND_URL + path, timeout=10) as resp:
        return json.loads(resp.read())


def main() -> int:
    print(f"Backend: {BACKEND_URL}")
    try:
        _http_get("/api/tasks")
    except Exception as e:
        print(f"FAIL: backend not reachable at {BACKEND_URL}: {e}")
        print("Start it first with: cd src && uv run python server.py")
        return 1

    create_resp = _http_post(
        "/api/tasks",
        {
            "workflow_name": "_smoke",
            "workflow_inputs": {},
            "framework": "mngr-claude",
            "model": MODEL,
        },
    )
    task_id = create_resp["id"]
    print(f"Created task {task_id}")

    deadline = time.time() + TIMEOUT_SECONDS
    statuses_seen = set()
    final_task = None
    while time.time() < deadline:
        task = _http_get(f"/api/tasks/{task_id}")
        for step in task.get("steps", []):
            if step.get("last_status"):
                statuses_seen.add(step["last_status"][:80])
        status = task["status"]
        if status in ("completed", "failed"):
            final_task = task
            break
        time.sleep(1.5)

    if final_task is None:
        print(f"FAIL: task did not complete within {TIMEOUT_SECONDS}s")
        return 1

    print(f"Task ended with status={final_task['status']}")
    smoke_step = next((s for s in final_task["steps"] if s["stage"] == "smoke"), None)
    if smoke_step is None:
        print("FAIL: no `smoke` step in final task")
        return 1
    print(f"  step.session_id: {smoke_step.get('session_id')}")
    print(f"  step.outputs: {smoke_step.get('outputs')}")
    session_id = smoke_step.get("session_id")

    list_result = subprocess.run(
        ["mngr", "list", "--include", f'name == "{session_id}"', "--format", "jsonl"],
        check=False,
        capture_output=True,
        text=True,
    )
    agent_state = None
    agent_labels = {}
    for line in list_result.stdout.splitlines():
        try:
            d = json.loads(line)
            if d.get("name") == session_id:
                agent_state = d.get("state")
                agent_labels = d.get("labels") or {}
                break
        except json.JSONDecodeError:
            pass

    print(f"  mngr agent state: {agent_state}")
    print(f"  mngr agent labels: {agent_labels}")

    checks = [
        ("task completed", final_task["status"] == "completed"),
        ("session_id set", bool(session_id)),
        ("agent has app=ai-scientist label", agent_labels.get("app") == "ai-scientist"),
        (
            "agent has ai-scientist-task label",
            agent_labels.get("ai-scientist-task") == task_id,
        ),
        ("agent is STOPPED", agent_state == "STOPPED"),
        (
            "skill_ran in outputs",
            isinstance(smoke_step.get("outputs"), dict)
            and smoke_step["outputs"].get("skill_ran") is True,
        ),
        ("at least one live status update was seen", len(statuses_seen) > 0),
    ]
    print("\nChecks:")
    all_ok = True
    for label, passed in checks:
        marker = "OK" if passed else "FAIL"
        print(f"  [{marker}] {label}")
        all_ok = all_ok and passed

    if statuses_seen:
        print("\n  Status updates observed:")
        for s in sorted(statuses_seen):
            print(f"    - {s}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
