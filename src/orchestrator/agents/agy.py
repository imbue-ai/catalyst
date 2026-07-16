import os
import shlex
import logging
import subprocess
from typing import Dict, Any, Optional, Tuple, Callable

from .base import AGENT_TIMEOUT_SECS, parse_json_result
from .cli_base import BaseCliAgentRunner, make_subprocess_cancellable
from ..state import register_cancellable, unregister_cancellable

logger = logging.getLogger(__name__)


class AgyAgentRunner(BaseCliAgentRunner):
    def run(
        self,
        task_id: str,
        prompt: str,
        env_folder: str,
        stage: str,  # ignored by the direct runner
        common_environment_variables: Dict[str, str],
        model: Optional[str] = None,
        effort: Optional[str] = None,
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
        env.update(common_environment_variables)
        env["AGY_CLI_DISABLE_AUTO_UPDATE"] = "true"

        cmd = [
            "agy",
            # Antigravity sandboxing is currently unreliable:
            # With `--dangerously-skip-permissions`, bypassSandbox requests are auto-approved. At the same time, we're unable to allow-list network access upfront.
            # Hence, we run without sandboxing for the time being until agy has more mature sandbox configuration options.
            # "--sandbox",
            "--dangerously-skip-permissions",
            "--print-timeout",
            f"{AGENT_TIMEOUT_SECS}s",
            "--add-dir",
            abs_env_folder,
        ]
        if model:
            # Model name is the same string as returned by `agy models` (NOT the API model name).
            cmd.extend(["--model", model])
        cmd.extend(["-p", prompt])

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
            cancellable = make_subprocess_cancellable(process, label="agy")
            register_cancellable(task_id, cancellable)
            try:
                stdout_data, _ = process.communicate()
                returncode = process.returncode
            finally:
                unregister_cancellable(task_id, cancellable)

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
            data = parse_json_result(agent_raw_result)
            if data:
                return data, None, None

            return (
                None,
                None,
                f"Could not parse JSON output from Antigravity result string. Preview: {str(agent_raw_result)[:800]}...",
            )

        except Exception as e:
            return None, None, f"Antigravity execution error: {str(e)}"
