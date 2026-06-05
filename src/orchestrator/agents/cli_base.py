import json
import logging
import os
import re
import signal
import subprocess
from typing import Any, Callable, Dict, Optional, Tuple

from .base import AgentRunner
from ..state import Cancellable, register_cancellable, unregister_cancellable

logger = logging.getLogger(__name__)


def kill_process_group(proc: subprocess.Popen, timeout: float) -> None:
    """SIGTERM the process's session group, wait up to `timeout` for it
    to exit cleanly, then SIGKILL if it didn't. Idempotent: a dead
    process is a no-op. Direct CLI runners use this as their
    Cancellable's `cancel` closure."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError) as e:
        logger.debug(f"[PROCESS] SIGTERM skipped for pid {proc.pid}: {e}")
        return
    try:
        proc.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    logger.warning(
        f"[PROCESS] PID {proc.pid} didn't exit after {timeout}s, sending SIGKILL"
    )
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.wait(timeout=5)
    except Exception as e:
        logger.error(f"[PROCESS] SIGKILL failed for pid {proc.pid}: {e}")


def make_subprocess_cancellable(proc: subprocess.Popen, label: str = "") -> Cancellable:
    """Build the Cancellable wrapper a direct CLI runner registers for its
    subprocess. `label` is appended to the log description so cancellation
    messages name the runner (e.g. \"agy pid 1234\")."""
    description = f"{label} pid {proc.pid}".strip()
    return Cancellable(
        description=description,
        cancel=lambda timeout: kill_process_group(proc, timeout),
    )


class BaseCliAgentRunner(AgentRunner):
    """Common logic for CLI-based agents."""

    def _execute_cmd(
        self,
        task_id: str,
        cmd: list[str],
        abs_env_folder: str,
        env: dict,
        on_session_id: Optional[Callable[[str], None]] = None,
        on_data_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Tuple[str, Optional[str], int, list[str]]:
        """Common execution loop for stream-json output."""
        process = subprocess.Popen(
            cmd,
            cwd=abs_env_folder,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            close_fds=True,
            start_new_session=True,
        )
        cancellable = make_subprocess_cancellable(process, label=cmd[0])
        register_cancellable(task_id, cancellable)
        try:
            full_output = []
            session_id = None

            for line in iter(process.stdout.readline, ""):
                if line:
                    full_output.append(line)
                    json_match = re.search(r"(\{.*\})", line)
                    if json_match:
                        data = json.loads(json_match.group(1))

                        if not session_id:
                            if "session_id" in data:
                                session_id = data["session_id"]
                            elif "thread_id" in data:
                                session_id = data["thread_id"]
                                logger.debug(
                                    f"[AGENT] [{task_id[:8]}] Detected session ID from thread_id: {session_id}"
                                )
                            if session_id and on_session_id:
                                try:
                                    on_session_id(session_id)
                                except Exception as cb_err:
                                    logger.error(
                                        f"[AGENT] [{task_id[:8]}] Callback error: {cb_err}"
                                    )

                        if on_data_event:
                            on_data_event(data)

            process.wait()
            stdout = "".join(full_output)

            return stdout, session_id, process.returncode, full_output
        finally:
            unregister_cancellable(task_id, cancellable)

