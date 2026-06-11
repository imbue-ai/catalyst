import os
import shlex
import logging
from typing import Dict, Any, Optional, Tuple, Callable

from .base import AGENT_TIMEOUT_SECS, parse_json_result
from .cli_base import BaseCliAgentRunner

logger = logging.getLogger(__name__)


class CodexAgentRunner(BaseCliAgentRunner):
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
        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)
        env.update(common_environment_variables)
        abs_env_folder = os.path.abspath(env_folder)

        # Configure command options according to spec
        cmd = [
            "codex",
            "exec",
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--json",
            "-c",
            "sandbox_workspace_write.network_access=true",
            "-c",
            f"agents.job_max_runtime_seconds={AGENT_TIMEOUT_SECS}",
            "-c",
            "agents.max_threads=50",
        ]
        if model:
            cmd.extend(["--model", model])
        if effort:
            cmd.extend(["-c", f"model_reasoning_effort={effort}"])
        cmd.append(prompt)

        logger.debug(f"[AGENT] Starting Codex for task {task_id[:8]}")
        logger.debug(f"[AGENT] Executing in folder {abs_env_folder}: {shlex.join(cmd)}")

        last_agent_message_text = ""

        def handle_event(data: Dict[str, Any]):
            nonlocal last_agent_message_text

            # Track completed or updated agent messages to capture the final output
            if data.get("type") in ("item.completed", "item.updated"):
                item = data.get("item", {})
                if item.get("type") == "agent_message" and "text" in item:
                    last_agent_message_text = item.get("text", "")

            # Track active steps/command updates for user status reports
            if on_status:
                if data.get("type") == "item.started":
                    item = data.get("item", {})
                    item_type = item.get("type")
                    if item_type == "command_execution":
                        on_status(f"Running command: {item.get('command', '')}")
                elif data.get("type") == "item.completed":
                    item = data.get("item", {})
                    if item.get("type") == "agent_message" and "text" in item:
                        on_status(item.get("text", ""))

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
                f"[AGENT] [{task_id[:8]}] Codex finished with exit code {returncode}"
            )

            if returncode != 0:
                if returncode in [143, 137, -15, -9]:
                    return None, session_id, "Agent was interrupted/paused."

                stdout_tail = "".join(full_output)[-500:]
                return (
                    None,
                    session_id,
                    f"Codex failed with exit code {returncode}. Last output: {stdout_tail}",
                )

            data = parse_json_result(last_agent_message_text)
            if data:
                return data, session_id, None

            return (
                None,
                session_id,
                f"Could not parse JSON output from Codex result string. Preview: {str(last_agent_message_text)[:800]}...",
            )

        except Exception as e:
            return None, None, f"Codex execution error: {str(e)}"
