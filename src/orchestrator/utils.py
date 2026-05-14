import os
import subprocess
from typing import List

from context_manager import DEFAULT_DB_DIR
from .models import Task


def get_ai_scientist_path() -> str:
    return os.environ.get("AI_SCIENTIST_PATH", os.path.expanduser("~/.ai-scientist"))


def run_context_manager(task: Task, args: List[str]) -> str:
    abs_env_folder = os.path.abspath(task.env_folder)
    env = os.environ.copy()
    env["AI_SCIENTIST_DB_PATH"] = os.path.join(abs_env_folder, DEFAULT_DB_DIR)

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
