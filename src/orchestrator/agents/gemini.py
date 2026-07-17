import os
import json
import hashlib
import shlex
import logging
import threading
from typing import Dict, Any, Optional, Tuple, Callable

from .base import parse_json_result
from .cli_base import BaseCliAgentRunner

logger = logging.getLogger(__name__)


class GeminiAgentRunner(BaseCliAgentRunner):
    _ack_lock = threading.Lock()

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
        abs_env_folder = os.path.abspath(env_folder)
        custom_env = common_environment_variables.copy()
        custom_env["GEMINI_SYSTEM_MD"] = "1"

        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)
        env.update(custom_env)

        # Gemini CLI sandboxing requires environment variables to be specified via SANDBOX_ENV:
        env["SANDBOX_ENV"] = ",".join(
            f"{key}={value}" for key, value in custom_env.items()
        )

        self._acknowledge_scientist(abs_env_folder)

        cmd = [
            "gemini",
            "--approval-mode",
            "yolo",
        ]
        if not self.disable_sandboxing:
            cmd.append("--sandbox")
        cmd.extend([
            "--skip-trust",
            "--output-format",
            "stream-json",
        ])
        if model:
            cmd.extend(["--model", model])
        cmd.extend(["-p", prompt])

        logger.debug(f"[AGENT] Starting Gemini for task {task_id[:8]}")
        logger.debug(f"[AGENT] Executing: {shlex.join(cmd)}")

        assistant_content = []

        def handle_event(data):
            if data.get("type") == "message" and data.get("role") == "assistant":
                content = data.get("content")
                if content:
                    assistant_content.append(content)
            elif (
                data.get("type") == "tool_use"
                and data.get("tool_name") == "update_topic"
            ):
                summary = data.get("parameters", {}).get("summary")
                if summary and on_status:
                    on_status(summary)

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
                f"[AGENT] [{task_id[:8]}] Gemini finished with exit code {returncode}"
            )

            if returncode != 0:
                # 143 = SIGTERM, 137 = SIGKILL, -15 = SIGTERM, -9 = SIGKILL
                if returncode in [143, 137, -15, -9]:
                    return None, session_id, "Agent was interrupted/paused."

                stdout_tail = "".join(full_output)[-500:]
                return (
                    None,
                    session_id,
                    f"Gemini failed with exit code {returncode}. Last output: {stdout_tail}",
                )

            agent_raw_result = "".join(assistant_content)
            data = parse_json_result(agent_raw_result)
            if data:
                return data, session_id, None

            return (
                None,
                session_id,
                f"Could not parse JSON output from Gemini result string. Preview: {str(agent_raw_result)[:800]}...",
            )

        except Exception as e:
            return None, None, f"Gemini execution error: {str(e)}"

    def _acknowledge_scientist(self, env_folder: str) -> None:
        with self._ack_lock:
            try:
                ack_path = os.path.expanduser("~/.gemini/acknowledgments/agents.json")
                os.makedirs(os.path.dirname(ack_path), exist_ok=True)

                if os.path.exists(ack_path):
                    with open(ack_path, "r") as f:
                        try:
                            data = json.load(f)
                        except json.JSONDecodeError:
                            data = {}
                else:
                    data = {}

                env_folder_abs = os.path.abspath(env_folder)

                if env_folder_abs not in data:
                    data[env_folder_abs] = {}

                agent_def_path = os.path.join(
                    env_folder_abs, ".gemini/agents/scientist.md"
                )
                if os.path.exists(agent_def_path):
                    with open(agent_def_path, "rb") as f:
                        content = f.read()
                    current_hash = hashlib.sha256(content).hexdigest()

                    if data[env_folder_abs].get("scientist") != current_hash:
                        data[env_folder_abs]["scientist"] = current_hash
                        with open(ack_path, "w") as f:
                            json.dump(data, f, indent=2)
                else:
                    logger.warning(
                        f"Scientist agent definition not found at {agent_def_path}"
                    )
            except Exception as e:
                logger.warning(f"Failed to acknowledge scientist subagent: {e}")
