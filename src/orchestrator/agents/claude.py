import os
import shlex
import logging
from typing import Dict, Any, Optional, Tuple, Callable

from context_manager import DEFAULT_DB_DIR
from .base import parse_json_result
from .cli_base import BaseCliAgentRunner

logger = logging.getLogger(__name__)


class ClaudeAgentRunner(BaseCliAgentRunner):
    def run(
        self,
        task_id: str,
        prompt: str,
        env_folder: str,
        stage: str,  # ignored by the direct runner
        model: Optional[str] = None,
        tx_id: Optional[str] = None,
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        env = os.environ.copy()
        del env["VIRTUAL_ENV"]
        if tx_id:
            env["CONTEXT_TRANSACTION_ID"] = tx_id
        abs_env_folder = os.path.abspath(env_folder)
        env["UV_CACHE_DIR"] = os.path.join(abs_env_folder, "tmp/uv_cache")
        env["CATALYST_DB_PATH"] = os.path.join(abs_env_folder, DEFAULT_DB_DIR)
        env["MPLCONFIGDIR"] = os.path.join(abs_env_folder, "tmp/matplotlib_cache")
        env["CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR"] = "1"
        env["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"] = "1"
        env["BASH_DEFAULT_TIMEOUT_MS"] = "4000000"  # > 1 hour
        env["BASH_MAX_TIMEOUT_MS"] = "4000000"  # > 1 hour

        cmd = [
            "claude",
            "--dangerously-skip-permissions",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if model:
            cmd.extend(["--model", model])
        cmd.extend(["-p", prompt])

        logger.debug(f"[AGENT] Starting Claude for task {task_id[:8]}")
        logger.debug(f"[AGENT] Executing in folder {abs_env_folder}: {shlex.join(cmd)}")

        last_result_obj = {}
        last_error_messages = []

        def handle_event(data):
            if data.get("type") == "result":
                last_result_obj["data"] = data

            if data.get("type") == "assistant" and data.get("error"):
                error_message = data["error"]
                content_list = data.get("message", {}).get("content", [])
                if isinstance(content_list, list) and content_list:
                    for item in reversed(content_list):
                        if item.get("type") == "text":
                            error_message += f" - {item.get('text')}"

                last_error_messages.append(error_message)

            if on_status:
                status_text = None
                if data.get("type") == "assistant":
                    content_list = data.get("message", {}).get("content", [])
                    if isinstance(content_list, list) and content_list:
                        for item in reversed(content_list):
                            if item.get("type") == "text":
                                status_text = item.get("text")
                                break
                            elif item.get("type") == "thinking":
                                status_text = f"Thinking: {item.get('thinking')}"
                                break

                if status_text:
                    status_text = " ".join(status_text.split())
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
                f"[AGENT] [{task_id[:8]}] Claude finished with exit code {returncode}"
            )

            if returncode != 0:
                # 143 = SIGTERM, 137 = SIGKILL, -15 = SIGTERM, -9 = SIGKILL
                if returncode in [143, 137, -15, -9]:
                    return None, session_id, "Agent was interrupted/paused."

                stdout_tail = "".join(full_output)[-500:]
                last_error_message = (
                    last_error_messages[-1] if last_error_messages else ""
                )
                return (
                    None,
                    session_id,
                    f"{last_error_message}.\nClaude failed with exit code {returncode}. Last output: {stdout_tail}",
                )

            agent_raw_result = (
                last_result_obj.get("data", {}).get("result")
                if last_result_obj.get("data")
                else ""
            )
            data = parse_json_result(agent_raw_result)
            if data:
                return data, session_id, None

            return (
                None,
                session_id,
                f"Could not parse JSON output from Claude result string. Preview: {str(agent_raw_result)[:800]}...",
            )

        except Exception as e:
            return None, None, f"Claude execution error: {str(e)}"
