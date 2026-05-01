import os
import subprocess
from typing import List
from .models import Task

def run_context_manager(task: Task, args: List[str]) -> str:
    env = os.environ.copy()

    ctx_mgr_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "context_manager.py")
    )
    cmd = ["uv", "run", "python", ctx_mgr_path] + args
    result = subprocess.run(
        cmd,
        env=env,
        cwd=os.path.abspath(task.env_folder),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
