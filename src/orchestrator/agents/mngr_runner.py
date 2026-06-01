import contextlib
import enum
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
# tool_use events. mngr_claude writes here; mngr_antigravity writes to its
# own `antigravity/common_transcript` source (passed via `transcript_source`).
_COMMON_TRANSCRIPT_SOURCE = "claude/common_transcript"


class TurnCompletion(enum.Enum):
    """How a runner decides an agent's turn is finished.

    STOP_HOOK -- the agent type emits a `mngr/turn_complete` / `turn_end`
        event exactly once per turn (mngr_claude, via the Stop hook in
        `.claude/settings.local.json`). The most precise signal: it fires
        after the final assistant_message is flushed and never trips on
        intermediate idle.

    WAITING_STATE -- the agent type's plugin provisions an active-marker
        hook (mngr_antigravity 0.1.1+: PreInvocation touches the marker,
        Stop removes it) so `BaseAgent.get_lifecycle_state` reports RUNNING
        while the agent works and WAITING when idle. We use `mngr wait
        --state WAITING` as the turn-end signal.
    """

    STOP_HOOK = "stop_hook"
    WAITING_STATE = "waiting_state"


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

    Catalyst's skills are prompted to "output JSON as your final
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
    return f"cata-{short_task}-{safe_stage}-{suffix}"


class MngrAgentRunner(AgentRunner):
    """Drives an mngr-managed interactive agent for a single Catalyst step.

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
        transcript_source: str = _COMMON_TRANSCRIPT_SOURCE,
        turn_completion: TurnCompletion = TurnCompletion.STOP_HOOK,
        extra_env: Optional[Dict[str, str]] = None,
    ):
        self._agent_type = agent_type
        self._framework = framework
        self._agent_args_builder = agent_args_builder
        self._status_extractor = status_extractor
        self._assistant_text_extractor = assistant_text_extractor
        self._transcript_source = transcript_source
        self._turn_completion = turn_completion
        # Per-agent-type env vars layered on top of the shared set in run()
        # (e.g. mngr_claude's CLAUDE_CODE_DISABLE_BACKGROUND_TASKS,
        # mngr_antigravity's AGY_CLI_DISABLE_AUTO_UPDATE).
        self._extra_env = dict(extra_env) if extra_env else {}

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
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        abs_env_folder = os.path.abspath(env_folder)
        # One fallback for both the agent name and the label, so a user
        # filtering `mngr list` by catalyst-stage gets the same value
        # they see in the agent name.
        resolved_stage = stage or "step"
        agent_name = _generate_agent_name(task_id, resolved_stage)

        env_vars = {
            "UV_CACHE_DIR": os.path.join(abs_env_folder, "tmp/uv_cache"),
            "CATALYST_DB_PATH": os.path.join(abs_env_folder, DEFAULT_DB_DIR),
            "MPLCONFIGDIR": os.path.join(abs_env_folder, "tmp/matplotlib_cache"),
        }
        # Per-agent-type additions (see `extra_env` on __init__).
        env_vars.update(self._extra_env)
        if tx_id:
            env_vars["CONTEXT_TRANSACTION_ID"] = tx_id

        labels = {
            "app": "catalyst",
            "catalyst-task": task_id,
            "catalyst-stage": resolved_stage,
            "catalyst-framework": self._framework,
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
                if on_session_id:
                    try:
                        on_session_id(agent_name)
                    except Exception as cb_err:
                        logger.error(
                            f"[AGENT] [{task_id[:8]}] on_session_id error: {cb_err}"
                        )
                return self._wait_and_harvest(task_id, agent_name, on_status)

        except Exception as e:
            return None, agent_name, f"{self._framework} execution error: {e}"

        finally:
            try:
                os.unlink(prompt_file.name)
            except OSError:
                pass

    def resume_in_place(
        self,
        task_id: str,
        agent_name: str,
        env_folder: str,
        model: Optional[str] = None,
        tx_id: Optional[str] = None,
        stage: Optional[str] = None,
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """Restart an existing (stopped) mngr agent and nudge it to finish.

        Called by the orchestrator when a step is being resumed and the
        Step already has a `session_id` from its prior run. Calls
        `mngr start <agent>` (the agent's tmux session, env file,
        work_dir, and transcript are all preserved on disk), then sends
        "Continue where you left off." via `mngr message --message-file`.
        The agent picks up its existing conversation context and emits
        a new turn ending in JSON. We then run the same wait + harvest
        the fresh `run()` path does.

        `env_folder`, `model`, `tx_id`, and `stage` are accepted for
        interface parity with `run()`. They're already baked into the
        agent's env file from the original create; we don't re-send them.

        On `mngr start` failure (agent was destroyed, work_dir is gone,
        etc.) returns a `"resume_unrecoverable: ..."` error so the
        orchestrator can fall back to a fresh `run()` call.
        """
        del env_folder, model, tx_id, stage  # already baked into the agent's env file

        try:
            start_result = subprocess.run(
                ["mngr", "start", agent_name],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            return None, agent_name, f"resume_unrecoverable: mngr CLI not found on PATH: {e}"

        if start_result.returncode != 0:
            tail = ((start_result.stderr or "") + "\n" + (start_result.stdout or ""))[-1500:]
            return (
                None,
                agent_name,
                f"resume_unrecoverable: mngr start failed (exit {start_result.returncode}). "
                f"stderr+stdout tail:\n{tail}",
            )

        prompt_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, prefix=f"{agent_name}-resume-"
        )
        try:
            prompt_file.write("Continue where you left off.")
            prompt_file.close()

            try:
                message_result = subprocess.run(
                    [
                        "mngr",
                        "message",
                        agent_name,
                        "--message-file",
                        prompt_file.name,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as e:
                return None, agent_name, f"resume_unrecoverable: mngr CLI not found on PATH: {e}"

            if message_result.returncode != 0:
                tail = ((message_result.stderr or "") + "\n" + (message_result.stdout or ""))[-1500:]
                return (
                    None,
                    agent_name,
                    f"mngr message failed (exit {message_result.returncode}). "
                    f"stderr+stdout tail:\n{tail}",
                )

            with self._registered_agent(task_id, agent_name):
                if on_session_id:
                    try:
                        on_session_id(agent_name)
                    except Exception as cb_err:
                        logger.error(
                            f"[AGENT] [{task_id[:8]}] on_session_id error: {cb_err}"
                        )
                return self._wait_and_harvest(task_id, agent_name, on_status)

        except Exception as e:
            return None, agent_name, f"{self._framework} resume execution error: {e}"

        finally:
            try:
                os.unlink(prompt_file.name)
            except OSError:
                pass

    def _wait_and_harvest(
        self,
        task_id: str,
        agent_name: str,
        on_status: Optional[Callable[[str], None]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """Shared "wait for turn_end, then parse the final assistant
        text" path used by both `run()` and `resume_in_place()`."""
        del task_id  # only used for log prefix today; kept on the signature for future use
        saw_turn_end = self._wait_for_turn_end(agent_name, on_status)
        if not saw_turn_end:
            # The turn never completed and the agent was stopped (either
            # the deadline expired or the agent was stopped externally,
            # e.g. the user clicked Pause). Distinguishing here would
            # require us to read task state, so we leave the message
            # generic and let the orchestrator's task-status check
            # overwrite it with "Paused" when appropriate.
            return (None, agent_name, self._no_completion_error())

        assistant_text = self._read_assistant_text(agent_name, on_status)

        data = parse_json_result(assistant_text)
        if data:
            return data, agent_name, None

        return (
            None,
            agent_name,
            f"Could not parse JSON output from {self._framework} result. Preview: {assistant_text[:800]}...",
        )

    def _no_completion_error(self) -> str:
        """Error string for the case where the turn never completed.

        Phrased per the turn-completion strategy so the message points at
        the actual failure mode rather than a generic one.
        """
        if self._turn_completion is TurnCompletion.WAITING_STATE:
            return (
                f"Agent never reached the WAITING lifecycle state "
                f"(deadline was {_WAIT_TIMEOUT_SECONDS}s). {self._framework} "
                "completion is signalled when the agent's per-task active "
                "marker is cleared; a timeout means either the agent never "
                "finished its turn, the plugin's hooks didn't fire, or it "
                "was paused / stopped externally."
            )
        return (
            f"Agent stopped without signaling turn_end "
            f"(deadline was {_WAIT_TIMEOUT_SECONDS}s). If this wasn't a "
            "manual pause, the env_folder may pre-date the change that "
            "added the Stop hook to .claude/settings.local.json -- delete "
            "the task and recreate it to pick up the new env_folder template."
        )

    def _wait_for_turn_end(
        self,
        agent_name: str,
        on_status: Optional[Callable[[str], None]],
    ) -> bool:
        """Block until the agent's turn finishes (or it is stopped).

        Dispatches to the strategy configured at construction. Returns True
        iff the turn completed normally; False covers both the deadline
        expiring and an external stop (pause/cancel) -- the orchestrator
        distinguishes by checking the task's status after run() returns.
        """
        if self._turn_completion is TurnCompletion.WAITING_STATE:
            return self._wait_for_turn_end_waiting_state(agent_name, on_status)
        return self._wait_for_turn_end_stop_hook(agent_name, on_status)

    def _spawn_stopped_watcher(
        self, agent_name: str, done: threading.Event
    ) -> Tuple[subprocess.Popen, threading.Thread]:
        """Spawn `mngr wait --state STOPPED` and a thread that sets `done`
        when it returns.

        Shared by both turn-completion strategies: it's how a pause / cancel
        (server.py calls `mngr stop` via `cancel_task_process`) unblocks the
        runner instead of leaving it parked for the full timeout while the
        dashboard still shows the step RUNNING.
        """
        wait_proc = subprocess.Popen(
            [
                "mngr",
                "wait",
                agent_name,
                "--state",
                "STOPPED",
                "--timeout",
                f"{_WAIT_TIMEOUT_SECONDS}s",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        def watch_stopped() -> None:
            # rc=0 means the agent reached STOPPED state, rc=2 means wait
            # timed out (we'll have hit our own deadline by then). Either
            # way, the runner should exit.
            wait_proc.wait()
            done.set()

        wait_thread = threading.Thread(target=watch_stopped, daemon=True)
        wait_thread.start()
        return wait_proc, wait_thread

    @staticmethod
    def _terminate_proc(proc: subprocess.Popen) -> None:
        """Best-effort terminate -> wait -> kill of a helper subprocess.

        Same shape as mngr's own RunningProcess.terminate: SIGTERM, give it
        5s, SIGKILL on timeout.
        """
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

    def _wait_for_turn_end_stop_hook(
        self,
        agent_name: str,
        on_status: Optional[Callable[[str], None]],
    ) -> bool:
        """Turn-end detection for agent types that emit a `turn_end` event
        (STOP_HOOK strategy; mngr_claude).

        `mngr event --follow` streams transcript events; on a `turn_end`
        event from the `mngr/turn_complete` source we set `saw_turn_end`.
        Every event also feeds `status_extractor` so the dashboard's
        per-step status stays current. A parallel `mngr wait --state
        STOPPED` catches external pause/cancel.
        """
        deadline = time.monotonic() + _WAIT_TIMEOUT_SECONDS
        saw_turn_end = threading.Event()
        done = threading.Event()

        event_proc = subprocess.Popen(
            [
                "mngr",
                "event",
                agent_name,
                "--follow",
                "--format",
                "jsonl",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        wait_proc, wait_thread = self._spawn_stopped_watcher(agent_name, done)

        def consume_events() -> None:
            assert event_proc.stdout is not None
            for line in event_proc.stdout:
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
                    done.set()
                    return

        event_thread = threading.Thread(target=consume_events, daemon=True)
        event_thread.start()

        try:
            remaining = max(0.0, deadline - time.monotonic())
            done.wait(timeout=remaining)
        finally:
            self._terminate_proc(event_proc)
            self._terminate_proc(wait_proc)
            event_thread.join(timeout=5)
            wait_thread.join(timeout=5)
        return saw_turn_end.is_set()

    def _wait_for_turn_end_waiting_state(
        self,
        agent_name: str,
        on_status: Optional[Callable[[str], None]],
    ) -> bool:
        """Turn-end detection via the WAITING lifecycle state
        (WAITING_STATE strategy; mngr_antigravity 0.1.1+).

        The plugin provisions an active-marker hook (PreInvocation creates
        it, Stop removes it) so `BaseAgent.get_lifecycle_state` reports
        RUNNING while the agent works and WAITING when idle. We block on
        `mngr wait --state WAITING`; rc=0 means the turn finished. A
        parallel STOPPED watcher catches external pause/cancel, and an
        `mngr event --follow` is consumed in the background purely for
        status updates -- the turn-end signal comes from `mngr wait`, so
        the event stream is never inspected for transcript content here.
        """
        deadline = time.monotonic() + _WAIT_TIMEOUT_SECONDS
        saw_turn_end = threading.Event()
        done = threading.Event()

        event_proc = subprocess.Popen(
            [
                "mngr",
                "event",
                agent_name,
                "--follow",
                "--format",
                "jsonl",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        stop_proc, stop_thread = self._spawn_stopped_watcher(agent_name, done)

        wait_proc = subprocess.Popen(
            [
                "mngr",
                "wait",
                agent_name,
                "--state",
                "WAITING",
                "--timeout",
                f"{_WAIT_TIMEOUT_SECONDS}s",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        def watch_waiting() -> None:
            rc = wait_proc.wait()
            if rc == 0:
                saw_turn_end.set()
            done.set()

        def consume_events() -> None:
            assert event_proc.stdout is not None
            for line in event_proc.stdout:
                if not line.strip() or not on_status:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                status = self._status_extractor(event)
                if status:
                    try:
                        on_status(status)
                    except Exception as cb_err:
                        logger.error(f"[AGENT] on_status error: {cb_err}")

        wait_thread = threading.Thread(target=watch_waiting, daemon=True)
        wait_thread.start()
        event_thread = threading.Thread(target=consume_events, daemon=True)
        event_thread.start()

        try:
            remaining = max(0.0, deadline - time.monotonic())
            done.wait(timeout=remaining)
        finally:
            self._terminate_proc(event_proc)
            self._terminate_proc(wait_proc)
            self._terminate_proc(stop_proc)
            event_thread.join(timeout=5)
            wait_thread.join(timeout=5)
            stop_thread.join(timeout=5)
        return saw_turn_end.is_set()

    def _read_transcript_events(self, agent_name: str) -> List[Dict[str, Any]]:
        """Read the agent's common transcript as a list of parsed events,
        in file order. Returns [] if the source has no events yet."""
        result = subprocess.run(
            [
                "mngr",
                "event",
                agent_name,
                "--source",
                self._transcript_source,
                "--format",
                "jsonl",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        events: List[Dict[str, Any]] = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events

    def _read_assistant_text(
        self,
        agent_name: str,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Read every assistant_message in the agent's transcript,
        concatenated. Called after `_wait_for_turn_end` confirms the
        turn is done.

        Polls with a short bounded budget because the common-transcript
        converters (mngr_claude's and mngr_antigravity's both) write
        `events/<source>/common_transcript/events.jsonl` on a ~5s timer,
        while our turn-end signal can fire sooner. Without a wait here, a
        fast turn could be detected as done before the conversion sees the
        assistant_message and we'd return empty text.

        If `on_status` is given, fire a status callback for every event
        as a backstop -- a fast turn can finish before the live
        follower in `_wait_for_turn_end` ever sees the assistant_message
        event. Driving on_status here guarantees the dashboard's
        last_status field reflects the final output even in that race.
        """
        deadline = time.monotonic() + _POST_TURN_END_POLL_SECONDS
        seen_event_ids: set[str] = set()
        while True:
            parts: List[str] = []
            for event in self._read_transcript_events(agent_name):
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
