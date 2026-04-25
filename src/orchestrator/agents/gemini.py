import os
import shlex
from typing import Dict, Any, Optional, Tuple, Callable
from .cli_base import BaseCliAgentRunner

class GeminiAgentRunner(BaseCliAgentRunner):
    def run(
        self,
        task_id: str,
        prompt: str,
        env_folder: str,
        db_path: str,
        model: Optional[str] = None,
        on_session_id: Optional[Callable[[str], None]] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        env = os.environ.copy()
        env["AI_SCIENTIST_DB_PATH"] = db_path
        abs_env_folder = os.path.abspath(env_folder)

        cmd = ["gemini", "--yolo", "--output-format", "stream-json"]
        if model:
            cmd.extend(["--model", model])
        cmd.extend(["-p", prompt])

        print(f"[AGENT] Starting Gemini for task {task_id[:8]}")
        print(f"[AGENT] Executing: {shlex.join(cmd)}")

        try:
            agent_raw_result, session_id, returncode, full_output = self._execute_cmd(
                task_id, cmd, abs_env_folder, env, on_session_id
            )
            
            print(f"[AGENT] [{task_id[:8]}] Gemini finished with exit code {returncode}")
            
            if returncode != 0:
                stdout_tail = "".join(full_output)[-500:]
                return None, session_id, f"Gemini failed with exit code {returncode}. Last output: {stdout_tail}"

            data = self._parse_json_result(agent_raw_result)
            if data:
                return data, session_id, None

            return None, session_id, f"Could not parse JSON output from Gemini result string. Preview: {str(agent_raw_result)[:200]}..."

        except Exception as e:
            return None, None, f"Gemini execution error: {str(e)}"
