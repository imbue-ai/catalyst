import os
import subprocess
from typing import List

from context_manager import DEFAULT_DB_DIR
from .models import Task


def get_catalyst_path() -> str:
    path = os.environ.get("CATALYST_PATH")
    if path:
        return path

    catalyst_path = os.path.expanduser("~/.catalyst")
    legacy_path = os.path.expanduser("~/.ai-scientist")
    if not os.path.exists(catalyst_path) and os.path.exists(legacy_path):
        return legacy_path
    return catalyst_path


# Default Catalyst's `mngr` host_dir to an isolated location so Catalyst's
# agents don't mix into the user's main `~/.mngr` and the runner's `mngr`
# calls aren't blocked by stale fields in the user's profile settings
# (e.g. `plugins.kanpan.column_order`). Set via `setdefault` so an explicit
# `MNGR_HOST_DIR=...` export wins.
os.environ.setdefault("MNGR_HOST_DIR", os.path.expanduser("~/.mngr-catalyst"))


def run_context_manager(task: Task, args: List[str]) -> str:
    abs_env_folder = os.path.abspath(task.env_folder)
    env = os.environ.copy()
    env["CATALYST_DB_PATH"] = os.path.join(abs_env_folder, DEFAULT_DB_DIR)

    ctx_mgr_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "context_manager.py")
    )
    cmd = ["uv", "run", "python", ctx_mgr_path] + args
    try:
        result = subprocess.run(
            cmd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed with exit code {e.returncode}"
        if e.stderr:
            error_msg += f"\n\nStderr:\n{e.stderr.strip()}"
        if e.stdout:
            error_msg += f"\n\nStdout:\n{e.stdout.strip()}"
        raise Exception(error_msg) from e
