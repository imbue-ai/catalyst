import json
import logging
import os
import re
import secrets
import shlex
import subprocess
import tempfile
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from context_manager import DEFAULT_DB_DIR
from .base import AgentRunner
from ..state import register_agent, unregister_agent

logger = logging.getLogger(__name__)


# How long `mngr wait` may block before we give up on this turn (seconds).
# Long enough for any single skill turn to finish, short enough to bound a hang.
_WAIT_TIMEOUT_SECONDS = 60 * 60

# Source path (under the agent's events/ dir) that carries the normalized
# transcript for any agent type that maps onto Anthropic-style assistant /
# tool_use events. mngr_claude writes here; mngr_gemini is expected to do
# the same per the cross-cutting plugin contract.
_COMMON_TRANSCRIPT_SOURCE = "claude/common_transcript"


def parse_json_result(raw_result: Any) -> Optional[Dict[str, Any]]:
    """Extract a JSON object out of an agent's freeform final assistant text.

    ai-scientist's skills are prompted to "output JSON as your final
    message" but the wrapping varies: sometimes a fenced ```json block,
    sometimes raw text containing braces. Migrating every skill to a
    structured tool_use convention is tracked as a follow-up; until then
    this regex/brace-walk is the bridge.
    """
    if isinstance(raw_result, dict):
        return raw_result

    text = str(raw_result)

    json_blocks = re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_blocks:
        try:
            return json.loads(json_blocks[-1])
        except json.JSONDecodeError:
            pass

    last_brace = text.rfind("}")
    while last_brace != -1:
        balance = 0
        for i in range(last_brace, -1, -1):
            if text[i] == "}":
                balance += 1
            elif text[i] == "{":
                balance -= 1
                if balance == 0:
                    obj_str = text[i : last_brace + 1]
                    try:
                        data = json.loads(obj_str)
                        if isinstance(data, dict):
                            return data
                    except json.JSONDecodeError:
                        break

        last_brace = text.rfind("}", 0, last_brace)

    return None


def _generate_agent_name(task_id: str, stage: str) -> str:
    short_task = task_id.split("_")[-1][:8] if "_" in task_id else task_id[:8]
    safe_stage = re.sub(r"[^a-z0-9-]", "-", stage.lower())[:32].strip("-") or "step"
    suffix = secrets.token_hex(3)
    return f"aisci-{short_task}-{safe_stage}-{suffix}"


class MngrAgentRunner(AgentRunner):
    """Drives an mngr-managed interactive agent for a single ai-scientist step.

    Lifecycle per `run()` call:
        1. mngr create --no-connect ...    (returns once agent is spawned)
        2. mngr event --follow             (background, accumulates assistant text)
        3. mngr wait --state WAITING ...   (blocks until turn finishes)
        4. mngr stop                       (halts cleanly; transcript preserved)

    Stopped agents stay visible in `mngr list` for `mngr connect` /
    `mngr transcript` post-mortem; explicit cleanup via `mngr destroy` is
    a separate user-invoked path.
    """

    def __init__(
        self,
        agent_type: str,
        framework: str,
        agent_args_builder: Callable[[Optional[str]], List[str]],
        status_extractor: Callable[[Dict[str, Any]], Optional[str]],
        assistant_text_extractor: Callable[[Dict[str, Any]], Optional[str]],
    ):
        self._agent_type = agent_type
        self._framework = framework
        self._agent_args_builder = agent_args_builder
        self._status_extractor = status_extractor
        self._assistant_text_extractor = assistant_text_extractor

    def run(
        self,
        task_id: str,
        prompt: str,
        env_folder: str,
        model: Optional[str] = None,
        tx_id: Optional[str] = None,
        stage: Optional[str] = None,
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        abs_env_folder = os.path.abspath(env_folder)
        agent_name = _generate_agent_name(task_id, stage or "step")

        env_vars = {
            "UV_CACHE_DIR": os.path.join(abs_env_folder, "tmp/uv_cache"),
            "AI_SCIENTIST_DB_PATH": os.path.join(abs_env_folder, DEFAULT_DB_DIR),
            "MPLCONFIGDIR": os.path.join(abs_env_folder, "tmp/matplotlib_cache"),
        }
        if tx_id:
            env_vars["CONTEXT_TRANSACTION_ID"] = tx_id

        labels = {
            "app": "ai-scientist",
            "ai-scientist-task": task_id,
            "ai-scientist-stage": stage or "unknown",
            "ai-scientist-framework": self._framework,
        }

        prompt_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, prefix=f"{agent_name}-"
        )
        try:
            prompt_file.write(prompt)
            prompt_file.close()

            create_cmd = [
                "mngr",
                "create",
                agent_name,
                "--type",
                self._agent_type,
                "--from",
                f":{abs_env_folder}",
                "--transfer",
                "none",
                "--no-connect",
                "--message-file",
                prompt_file.name,
            ]
            for key, value in labels.items():
                create_cmd.extend(["--label", f"{key}={value}"])
            for key, value in env_vars.items():
                create_cmd.extend(["--env", f"{key}={value}"])

            agent_args = self._agent_args_builder(model)
            if agent_args:
                create_cmd.append("--")
                create_cmd.extend(agent_args)

            logger.debug(
                f"[AGENT] [{task_id[:8]}] {self._framework} via mngr: {shlex.join(create_cmd)}"
            )

            try:
                create_result = subprocess.run(
                    create_cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as e:
                return None, None, f"mngr CLI not found on PATH: {e}"

            if create_result.returncode != 0:
                tail = (create_result.stderr or create_result.stdout or "")[-800:]
                return (
                    None,
                    None,
                    f"mngr create failed (exit {create_result.returncode}): {tail}",
                )

            register_agent(task_id, agent_name)
            if on_session_id:
                try:
                    on_session_id(agent_name)
                except Exception as cb_err:
                    logger.error(f"[AGENT] [{task_id[:8]}] on_session_id error: {cb_err}")

            assistant_buffer: List[str] = []
            event_proc, event_thread = self._spawn_event_follower(
                agent_name, assistant_buffer, on_status
            )

            try:
                wait_proc = subprocess.run(
                    [
                        "mngr",
                        "wait",
                        agent_name,
                        "--state",
                        "WAITING",
                        "--state",
                        "DONE",
                        "--state",
                        "STOPPED",
                        "--timeout",
                        f"{_WAIT_TIMEOUT_SECONDS}s",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            finally:
                self._shutdown_event_follower(event_proc, event_thread)

            wait_rc = wait_proc.returncode

            self._stop_agent(agent_name, task_id)
            unregister_agent(task_id, agent_name)

            if wait_rc == 2:
                return (
                    None,
                    agent_name,
                    f"Agent did not reach WAITING/DONE within {_WAIT_TIMEOUT_SECONDS}s; stopped.",
                )
            if wait_rc != 0:
                tail = (wait_proc.stderr or wait_proc.stdout or "")[-500:]
                return None, agent_name, f"mngr wait failed (exit {wait_rc}): {tail}"

            assistant_text = "".join(assistant_buffer)
            data = parse_json_result(assistant_text)
            if data:
                return data, agent_name, None

            return (
                None,
                agent_name,
                f"Could not parse JSON output from {self._framework} result. Preview: {assistant_text[:800]}...",
            )

        except Exception as e:
            unregister_agent(task_id, agent_name)
            return None, agent_name, f"{self._framework} execution error: {e}"

        finally:
            try:
                os.unlink(prompt_file.name)
            except OSError:
                pass

    def _spawn_event_follower(
        self,
        agent_name: str,
        assistant_buffer: List[str],
        on_status: Optional[Callable[[str], None]],
    ) -> Tuple[subprocess.Popen, threading.Thread]:
        cmd = [
            "mngr",
            "event",
            agent_name,
            "--source",
            _COMMON_TRANSCRIPT_SOURCE,
            "--follow",
            "--format",
            "jsonl",
        ]
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        def consume() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = self._assistant_text_extractor(event)
                if text:
                    assistant_buffer.append(text)
                if on_status:
                    status = self._status_extractor(event)
                    if status:
                        try:
                            on_status(status)
                        except Exception as cb_err:
                            logger.error(f"[AGENT] on_status error: {cb_err}")

        thread = threading.Thread(target=consume, daemon=True)
        thread.start()
        return proc, thread

    def _shutdown_event_follower(
        self, proc: subprocess.Popen, thread: threading.Thread
    ) -> None:
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass
        thread.join(timeout=5)

    def _stop_agent(self, agent_name: str, task_id: str) -> None:
        result = subprocess.run(
            ["mngr", "stop", agent_name],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning(
                f"[AGENT] [{task_id[:8]}] mngr stop {agent_name} failed: "
                f"{(result.stderr or result.stdout)[:300]}"
            )
