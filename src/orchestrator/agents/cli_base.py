import subprocess
import os
import re
import json
import shlex
import logging
from typing import Dict, Any, Optional, Tuple, Callable
from .base import AgentRunner
from ..state import register_process, unregister_process

logger = logging.getLogger(__name__)


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
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, Optional[str], int, list[str]]:
        """Common execution loop for stream-json output."""
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

            full_output = []
            session_id = None

            for line in iter(process.stdout.readline, ""):
                if line:
                    full_output.append(line)
                    try:
                        json_match = re.search(r"(\{.*\})", line)
                        if json_match:
                            data = json.loads(json_match.group(1))

                            if not session_id and "session_id" in data:
                                session_id = data["session_id"]
                                logger.debug(
                                    f"[AGENT] [{task_id[:8]}] Detected session ID: {session_id}"
                                )
                                if on_session_id:
                                    try:
                                        on_session_id(session_id)
                                    except Exception as cb_err:
                                        logger.error(
                                            f"[AGENT] [{task_id[:8]}] Callback error: {cb_err}"
                                        )

                            if on_data_event:
                                on_data_event(data)
                    except Exception:
                        pass

            process.wait()
            stdout = "".join(full_output)
            unregister_process(task_id, process)

            return stdout, session_id, process.returncode, full_output

        except Exception as e:
            # Attempt to unregister if process exists
            if "process" in locals():
                unregister_process(task_id, process)
            raise e

    def _parse_json_result(self, raw_result: Any) -> Optional[Dict[str, Any]]:
        if isinstance(raw_result, dict):
            return raw_result

        # 1. Try to find the last ```json block
        json_blocks = re.findall(r"```json\s*(.*?)\s*```", str(raw_result), re.DOTALL)
        if json_blocks:
            try:
                return json.loads(json_blocks[-1])
            except json.JSONDecodeError:
                pass

        # 2. Try to find the last {...}
        all_objects = re.findall(r"(\{.*?\})", str(raw_result), re.DOTALL)
        if all_objects:
            for obj_str in reversed(all_objects):
                try:
                    data = json.loads(obj_str)
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    continue
        return None
