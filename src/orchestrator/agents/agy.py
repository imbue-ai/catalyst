import os
import shlex
import logging
from typing import Dict, Any, Optional, Tuple, Callable

from .base import AGENT_TIMEOUT_SECS, parse_json_result
from .cli_base import BaseCliAgentRunner

logger = logging.getLogger(__name__)


class AgyAgentRunner(BaseCliAgentRunner):
    def __init__(self, disable_sandboxing: bool = False) -> None:
        super().__init__()
        self.disable_sandboxing = disable_sandboxing

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
            "--dangerously-skip-permissions",
            "--output-format",
            "stream-json",
            "--print-timeout",
            f"{AGENT_TIMEOUT_SECS}s",
            "--add-dir",
            abs_env_folder,
        ]
        # Antigravity sandboxing is currently unreliable:
        # With `--dangerously-skip-permissions`, bypassSandbox requests are auto-approved. At the same time, we're unable to allow-list network access upfront.
        # Hence, we run without sandboxing for the time being until agy has more mature sandbox configuration options.
        # if not self.disable_sandboxing:
        #     cmd.append("--sandbox")
        if model:
            # Model name is the same string as returned by `agy models` (NOT the API model name).
            cmd.extend(["--model", model])
        cmd.extend(["-p", prompt])

        logger.debug(f"[AGENT] Starting Antigravity for task {task_id[:8]}")
        logger.debug(f"[AGENT] Executing in folder {abs_env_folder}: {shlex.join(cmd)}")

        last_result_obj = {}
        current_step_index = None
        current_step_text = ""

        def handle_event(data: Dict[str, Any]):
            nonlocal current_step_index, current_step_text

            if data.get("event") == "result":
                last_result_obj["data"] = data.get("result", {})

            step_update = data.get("step_update", {})
            if step_update:
                step_index = step_update.get("step_index")
                if step_index != current_step_index:
                    current_step_index = step_index
                    current_step_text = ""

                if on_status:
                    status_text = None
                    step_type = step_update.get("step_type")
                    if step_type == "tool":
                        tool_name = step_update.get("tool_name") or step_update.get("tool_info", {}).get("name")
                        if tool_name == "run_command":
                            cmd_line = step_update.get("tool_info", {}).get("parameters", {}).get("CommandLine")
                            if cmd_line:
                                status_text = f"Running command: {cmd_line}"
                            else:
                                status_text = "Running command"
                        elif tool_name:
                            status_text = f"Using tool: {tool_name}"
                    elif step_type == "agent_response":
                        text_delta = step_update.get("text_delta")
                        if text_delta:
                            current_step_text += text_delta
                            status_text = current_step_text

                    if status_text:
                        on_status(status_text)

        try:
            stdout, session_id, returncode, full_output = self._execute_cmd(
                task_id,
                cmd,
                abs_env_folder,
                env,
                on_session_id,
                handle_event,
            )

            logger.debug(
                f"[AGENT] [{task_id[:8]}] Antigravity finished with exit code {returncode}"
            )

            if returncode != 0:
                # 143 = SIGTERM, 137 = SIGKILL, -15 = SIGTERM, -9 = SIGKILL
                if returncode in [143, 137, -15, -9]:
                    return None, session_id, "Agent was interrupted/paused."

                stdout_tail = "".join(full_output)[-500:]
                return (
                    None,
                    session_id,
                    f"Antigravity failed with exit code {returncode}. Last output: {stdout_tail}",
                )

            agent_raw_result = last_result_obj.get("data", {}).get("response", "")
            data = parse_json_result(agent_raw_result)
            if data:
                return data, session_id, None

            return (
                None,
                session_id,
                f"Could not parse JSON output from Antigravity result string. Preview: {str(agent_raw_result)[:800]}...",
            )

        except Exception as e:
            return None, None, f"Antigravity execution error: {str(e)}"
