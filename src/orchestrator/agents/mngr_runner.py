import contextlib
import json
import logging
import os
import re
import secrets
import shlex
import subprocess
import tempfile
import threading
import time
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from context_manager import DEFAULT_DB_DIR
from .base import AgentRunner
from ..state import register_agent, unregister_agent
# Ensures the process-wide MNGR_HOST_DIR default is set before any
# subprocess `mngr` call inherits os.environ.
from .. import utils  # noqa: F401

logger = logging.getLogger(__name__)


# How long the runner may block waiting for a turn to finish (seconds).
# Multi-skill cascades (e.g. `/swarm` spawning Task subagents) can run
# for hours; this cap is generous on purpose. The agent's tmux session
# is the source of cost, not this timeout.
_WAIT_TIMEOUT_SECONDS = 4 * 60 * 60

# Source path (under the agent's events/ dir) that carries the normalized
# transcript for any agent type that maps onto Anthropic-style assistant /
# tool_use events. mngr_claude writes here; mngr_gemini is expected to do
# the same per the cross-cutting plugin contract.
_COMMON_TRANSCRIPT_SOURCE = "claude/common_transcript"

# Source + event-type written by the Stop hook in
# `src/claude_skills/settings.local.json`. Fires exactly once per agent
# turn, *after* the final assistant_message has been flushed to the
# transcript -- which is the signal we actually want, rather than mngr's
# WAITING state (which trips on every intermediate idle, including
# mid-swarm while Task subagents are running).
_TURN_COMPLETE_SOURCE = "mngr/turn_complete"
_TURN_END_EVENT_TYPE = "turn_end"

# How long to wait, after `turn_end` fires, for the assistant_message
# event to show up in `claude/common_transcript`. mngr_claude's
# `common_transcript.sh` polls Claude's raw session JSONL on a ~5s
# interval (see libs/mngr_claude/.../common_transcript.sh), so the
# Stop-hook-emitted `turn_end` event can outrun the converted
# assistant_message event by up to one poll cycle. We bound the
# read-side wait at twice that interval for safety.
_POST_TURN_END_POLL_SECONDS = 10.0
_POST_TURN_END_POLL_INTERVAL = 0.5


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

    @contextlib.contextmanager
    def _registered_agent(self, task_id: str, agent_name: str) -> Generator[None, None, None]:
        """Scope a registered agent to a `with` block: register on entry,
        always stop + unregister on exit. Used to centralize the
        "best-effort halt this agent no matter how we exit" pattern so
        every terminal path -- success, wait timeout, wait failure, or
        unexpected exception -- gets the same cleanup. `_stop_agent`
        already swallows and logs subprocess errors; we add an extra
        guard here so a stop failure can't mask the original exception
        when one is in flight.
        """
        register_agent(task_id, agent_name)
        try:
            yield
        finally:
            try:
                self._stop_agent(agent_name, task_id)
            except Exception as stop_err:
                logger.warning(
                    f"[AGENT] [{task_id[:8]}] failed to stop {agent_name} on exit: {stop_err}"
                )
            unregister_agent(task_id, agent_name)

    def run(
        self,
        task_id: str,
        prompt: str,
        env_folder: str,
        model: Optional[str] = None,
        tx_id: Optional[str] = None,
        stage: Optional[str] = None,
        on_agent_name: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        abs_env_folder = os.path.abspath(env_folder)
        # One fallback for both the agent name and the label, so a user
        # filtering `mngr list` by ai-scientist-stage gets the same value
        # they see in the agent name.
        resolved_stage = stage or "step"
        agent_name = _generate_agent_name(task_id, resolved_stage)

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
            "ai-scientist-stage": resolved_stage,
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
                combined = (create_result.stderr or "") + "\n" + (create_result.stdout or "")
                tail = combined[-1500:]
                return (
                    None,
                    None,
                    f"mngr create failed (exit {create_result.returncode}). "
                    f"stderr+stdout tail:\n{tail}",
                )

            with self._registered_agent(task_id, agent_name):
                if on_agent_name:
                    try:
                        on_agent_name(agent_name)
                    except Exception as cb_err:
                        logger.error(
                            f"[AGENT] [{task_id[:8]}] on_agent_name error: {cb_err}"
                        )

                saw_turn_end = self._wait_for_turn_end(agent_name, on_status)
                if not saw_turn_end:
                    return (
                        None,
                        agent_name,
                        f"Agent did not signal turn_end within "
                        f"{_WAIT_TIMEOUT_SECONDS}s. If this is an env_folder "
                        "created before the Stop-hook landed, delete the task "
                        "and recreate it so the new "
                        ".claude/settings.local.json (with the turn_end hook) "
                        "is in place.",
                    )

                assistant_text = self._read_assistant_text(agent_name, on_status)

                data = parse_json_result(assistant_text)
                if data:
                    return data, agent_name, None

                return (
                    None,
                    agent_name,
                    f"Could not parse JSON output from {self._framework} result. Preview: {assistant_text[:800]}...",
                )

        except Exception as e:
            return None, agent_name, f"{self._framework} execution error: {e}"

        finally:
            try:
                os.unlink(prompt_file.name)
            except OSError:
                pass

    def _wait_for_turn_end(
        self,
        agent_name: str,
        on_status: Optional[Callable[[str], None]],
    ) -> bool:
        """Stream `mngr event --follow` and return when a `turn_end` event
        from the `mngr/turn_complete` source appears (or the deadline
        expires).

        The Stop hook in `src/claude_skills/settings.local.json` writes
        the `turn_end` event after the parent agent has truly finished
        emitting its final assistant_message -- including after a
        multi-skill cascade like `/swarm` where the parent goes through
        multiple intermediate idle states while waiting for Task
        subagents. Using this as the wait signal (instead of `mngr wait
        --state WAITING`) avoids the false-positive returns we used to
        hit mid-`/swarm`.

        While we wait, every event is also fed to `status_extractor` to
        keep the dashboard's per-step status field current.

        Returns True if `turn_end` was seen, False on timeout.
        """
        cmd = [
            "mngr",
            "event",
            agent_name,
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
        deadline = time.monotonic() + _WAIT_TIMEOUT_SECONDS
        saw_turn_end = threading.Event()

        def consume() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if on_status:
                    status = self._status_extractor(event)
                    if status:
                        try:
                            on_status(status)
                        except Exception as cb_err:
                            logger.error(f"[AGENT] on_status error: {cb_err}")
                if (
                    event.get("source") == _TURN_COMPLETE_SOURCE
                    and event.get("type") == _TURN_END_EVENT_TYPE
                ):
                    saw_turn_end.set()
                    return

        thread = threading.Thread(target=consume, daemon=True)
        thread.start()
        try:
            remaining = max(0.0, deadline - time.monotonic())
            saw_turn_end.wait(timeout=remaining)
        finally:
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
        return saw_turn_end.is_set()

    def _read_assistant_text(
        self,
        agent_name: str,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Read every assistant_message in the agent's transcript,
        concatenated. Called after `_wait_for_turn_end` confirms the
        turn is done.

        Polls with a short bounded budget because mngr_claude's
        `common_transcript.sh` converts Claude's raw session JSONL into
        `events/claude/common_transcript/events.jsonl` on a ~5s timer,
        while the Stop hook (and thus our `turn_end` signal) fires
        instantly. Without a wait here, a fast turn lands turn_end
        before the conversion sees the assistant_message and we'd
        return empty text.

        If `on_status` is given, fire a status callback for every event
        as a backstop -- a fast turn can finish before the live
        follower in `_wait_for_turn_end` ever sees the assistant_message
        event. Driving on_status here guarantees the dashboard's
        last_status field reflects the final output even in that race.
        """
        deadline = time.monotonic() + _POST_TURN_END_POLL_SECONDS
        seen_event_ids: set[str] = set()
        while True:
            result = subprocess.run(
                [
                    "mngr",
                    "event",
                    agent_name,
                    "--source",
                    _COMMON_TRANSCRIPT_SOURCE,
                    "--format",
                    "jsonl",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            parts: List[str] = []
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text = self._assistant_text_extractor(event)
                    if text:
                        parts.append(text)
                    if on_status:
                        event_id = event.get("event_id")
                        if event_id and event_id not in seen_event_ids:
                            seen_event_ids.add(event_id)
                            status = self._status_extractor(event)
                            if status:
                                try:
                                    on_status(status)
                                except Exception as cb_err:
                                    logger.error(
                                        f"[AGENT] on_status (post-turn) error: {cb_err}"
                                    )
            if parts or time.monotonic() >= deadline:
                return "".join(parts)
            time.sleep(_POST_TURN_END_POLL_INTERVAL)

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
