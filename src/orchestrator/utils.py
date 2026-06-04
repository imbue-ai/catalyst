import os
import subprocess
from typing import List

from context_manager import DEFAULT_DB_DIR
from .models import Task


def get_catalyst_path() -> str:
    path = os.environ.get("CATALYST_PATH")
    if path:
        return path

    catalyst_path = os.path.expanduser("~/catalyst-research")
    legacy_path = os.path.expanduser("~/.ai-scientist")
    if not os.path.exists(catalyst_path) and os.path.exists(legacy_path):
        return legacy_path
    return catalyst_path


# Catalyst's isolated `mngr` host_dir, kept separate from the user's main
# `~/.mngr` so Catalyst's agents don't mix in and the runner's `mngr` calls
# aren't blocked by stale fields in the user's profile settings (e.g.
# `plugins.kanpan.column_order`).
DEFAULT_MNGR_HOST_DIR = os.path.expanduser("~/.mngr-catalyst")


def mngr_env() -> dict[str, str]:
    """Build a subprocess env for any `mngr` CLI invocation: copy the
    parent env, then default `MNGR_HOST_DIR` to Catalyst's isolated
    host_dir if the caller hasn't already exported one. An explicit
    `MNGR_HOST_DIR=...` in the parent env wins.

    Applied per-subprocess (via `env=`) rather than via
    `os.environ.setdefault` at import time, so importing this module
    never mutates the catalyst server process's environment -- only the
    `mngr` child processes see the default.
    """
    env = os.environ.copy()
    env.setdefault("MNGR_HOST_DIR", DEFAULT_MNGR_HOST_DIR)
    return env


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
