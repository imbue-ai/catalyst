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
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        env = os.environ.copy()
        env["AI_SCIENTIST_DB_PATH"] = db_path
        abs_env_folder = os.path.abspath(env_folder)
        abs_source_folders = self._locate_source_folders(abs_env_folder)

        include_subdirectory_args = []
        for folder in abs_source_folders:
            include_subdirectory_args.extend(["--include-directories", folder])

        cmd = [
            "gemini",
            "--approval-mode",
            "default",
            "--policy",
            f"{abs_env_folder}/.gemini/policy.toml",
            "--skip-trust",
            "--output-format",
            "stream-json",
            *include_subdirectory_args,
        ]
        if model:
            cmd.extend(["--model", model])
        cmd.extend(["-p", prompt])

        print(f"[AGENT] Starting Gemini for task {task_id[:8]}")
        print(f"[AGENT] Executing: {shlex.join(cmd)}")

        assistant_content = []

        def handle_event(data):
            if data.get("type") == "message" and data.get("role") == "assistant":
                content = data.get("content")
                if content:
                    assistant_content.append(content)
                    if on_status:
                        last_line = (
                            "".join(assistant_content)
                            .replace(".", ".\n")
                            .strip()
                            .split("\n")[-1]
                        )
                        on_status(last_line)

        try:
            stdout, session_id, returncode, full_output = self._execute_cmd(
                task_id,
                cmd,
                abs_env_folder,
                env,
                on_session_id,
                handle_event,
                on_status,
            )

            print(
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
            data = self._parse_json_result(agent_raw_result)
            if data:
                return data, session_id, None

            return (
                None,
                session_id,
                f"Could not parse JSON output from Gemini result string. Preview: {str(agent_raw_result)[:200]}...",
            )

        except Exception as e:
            return None, None, f"Gemini execution error: {str(e)}"

    def _locate_source_folders(self, abs_env_folder: str) -> list[str]:
        # Traverse abs_env_folder, and collect all directories that contain symlink targets
        source_folders = set()
        for root, dirs, files in os.walk(abs_env_folder):
            for name in dirs + files:
                item_path = os.path.join(root, name)
                if os.path.islink(item_path):
                    target_path = os.readlink(item_path)
                    if not os.path.isabs(target_path):
                        target_path = os.path.join(root, target_path)
                        target_path = os.path.abspath(target_path)
                    # Add the parent folder of the target
                    source_folders.add(os.path.dirname(target_path))

        return list(source_folders)
