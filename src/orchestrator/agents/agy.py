import os
import shlex
import logging
import subprocess
from typing import Dict, Any, Optional, Tuple, Callable

from context_manager import DEFAULT_DB_DIR
from .cli_base import BaseCliAgentRunner
from ..state import register_process, unregister_process

logger = logging.getLogger(__name__)

PRINT_TIMEOUT = "6h"


class AgyAgentRunner(BaseCliAgentRunner):
    def run(
        self,
        task_id: str,
        prompt: str,
        env_folder: str,
        model: Optional[str] = None,
        tx_id: Optional[str] = None,
        stage: Optional[str] = None,  # ignored by the direct runner
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        # Check if the env_folder contains any hidden parent directories (e.g. .git, .venv) and raise an error if so, since that can cause Antigravity to fail to start
        abs_env_folder = os.path.abspath(env_folder)
        for parent in abs_env_folder.split(os.sep):
            if parent.startswith("."):
                return (
                    None,
                    None,
                    f"For Antigravity, environment folders cannot be inside a hidden directory like {parent}. Set CATALYST_PATH to a path that does not contain hidden directories.",
                )

        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)
        if tx_id:
            env["CONTEXT_TRANSACTION_ID"] = tx_id
        env["UV_CACHE_DIR"] = os.path.join(abs_env_folder, "tmp/uv_cache")
        env["CATALYST_DB_PATH"] = os.path.join(abs_env_folder, DEFAULT_DB_DIR)
        env["MPLCONFIGDIR"] = os.path.join(abs_env_folder, "tmp/matplotlib_cache")
        env["AGY_CLI_DISABLE_AUTO_UPDATE"] = "true"

        cmd = [
            "agy",
            "--sandbox",
            "--print-timeout",
            PRINT_TIMEOUT,
            "--add-dir",
            abs_env_folder,
            "-p",
            prompt,
        ]

        logger.debug(f"[AGENT] Starting Antigravity for task {task_id[:8]}")
        logger.debug(f"[AGENT] Executing in folder {abs_env_folder}: {shlex.join(cmd)}")

        try:
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
            register_process(task_id, process)

            stdout_data, _ = process.communicate()
            returncode = process.returncode
            unregister_process(task_id, process)

            logger.debug(
                f"[AGENT] [{task_id[:8]}] Antigravity finished with exit code {returncode}"
            )

            if returncode != 0:
                # 143 = SIGTERM, 137 = SIGKILL, -15 = SIGTERM, -9 = SIGKILL
                if returncode in [143, 137, -15, -9]:
                    return None, None, "Agent was interrupted/paused."

                stdout_tail = stdout_data[-500:]
                return (
                    None,
                    None,
                    f"Antigravity failed with exit code {returncode}. Last output: {stdout_tail}",
                )

            agent_raw_result = stdout_data
            data = self._parse_json_result(agent_raw_result)
            if data:
                return data, None, None

            return (
                None,
                None,
                f"Could not parse JSON output from Antigravity result string. Preview: {str(agent_raw_result)[:800]}...",
            )

        except Exception as e:
            # Attempt to unregister if process exists
            if "process" in locals():
                unregister_process(task_id, process)
            return None, None, f"Antigravity execution error: {str(e)}"
