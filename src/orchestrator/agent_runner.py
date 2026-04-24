import subprocess
import os
import re
import json
import time
from typing import Dict, Any, Optional, Tuple, Callable
from .state import register_process, unregister_process

def run_agent(
    task_id: str,
    framework: str,
    prompt: str,
    env_folder: str,
    db_path: str,
    model: Optional[str] = None,
    resume_session_id: Optional[str] = None,
    on_session_id: Optional[Callable[[str], None]] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Runs an agent and returns (json_output, session_id, error).
    """
    # Prepare environment
    env = os.environ.copy()
    env["AI_SCIENTIST_DB_PATH"] = db_path
    
    # Ensure env_folder exists and is absolute
    abs_env_folder = os.path.abspath(env_folder)
    if not os.path.exists(abs_env_folder):
        os.makedirs(abs_env_folder, exist_ok=True)

    # Command construction
    if framework == "gemini":
        cmd = ["gemini", "--yolo", "--output-format", "stream-json"]
        if resume_session_id:
            cmd.extend(["-s", resume_session_id])
        cmd.extend(["-p", prompt])
        if model:
            cmd.extend(["--model", model])
    elif framework == "claude":
        # Note: --output-format=stream-json requires --verbose with --print
        cmd = ["claude", "--dangerously-skip-permissions", "--output-format", "stream-json", "--verbose"]
        if resume_session_id:
            cmd.extend(["--resume", resume_session_id])
        cmd.extend(["-p", prompt])
        if model:
            cmd.extend(["--model", model])
    else:
        return None, None, f"Unknown framework: {framework}"

    # Run the command
    try:
        process = subprocess.Popen(
            cmd,
            cwd=abs_env_folder,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1 # Line buffered
        )
        register_process(task_id, process)
        
        full_stdout = []
        session_id = resume_session_id
        last_result_obj = None

        # Read stdout line by line
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                full_stdout.append(line)
                # Try to parse session_id early
                try:
                    # Some lines might have leading junk, try to find the JSON part
                    json_match = re.search(r"(\{.*\})", line)
                    if json_match:
                        data = json.loads(json_match.group(1))
                        if not session_id and "session_id" in data:
                            session_id = data["session_id"]
                            if on_session_id:
                                on_session_id(session_id)
                        
                        # In stream-json, the final result is often in a "type": "result" object
                        if data.get("type") == "result":
                            last_result_obj = data
                except Exception:
                    pass

        stdout = "".join(full_stdout)
        stderr = process.stderr.read()
        unregister_process(task_id)
        
        if process.returncode != 0:
            if process.returncode == -15 or process.returncode == -9:
                return None, session_id, "Process was cancelled."
            return None, session_id, f"Agent failed with exit code {process.returncode}. Stderr: {stderr}"
        
    except Exception as e:
        unregister_process(task_id)
        return None, resume_session_id, f"Execution error: {str(e)}"

    # Parse agent result
    # If we found a result object in the stream, use that
    if last_result_obj:
        agent_raw_result = last_result_obj.get("result")
    else:
        # Fallback to parsing whole stdout if stream parsing failed
        agent_raw_result = stdout

    if isinstance(agent_raw_result, dict):
        return agent_raw_result, session_id, None

    # Parse JSON from agent_raw_result
    json_match = re.search(r"```json\s*(.*?)\s*```", str(agent_raw_result), re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return data, session_id, None
        except json.JSONDecodeError:
            pass
            
    json_match = re.search(r"(\{.*\})", str(agent_raw_result), re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return data, session_id, None
        except json.JSONDecodeError:
            pass

    return None, session_id, "Could not parse JSON output from agent."
