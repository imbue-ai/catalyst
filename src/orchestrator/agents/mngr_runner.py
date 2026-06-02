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
from dataclasses import dataclass, field
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
# for hours; this cap is generous on purpose. Matches the timeout the
# direct Antigravity CLI runner uses. The agent's tmux session is the
# source of cost, not this timeout.
_WAIT_TIMEOUT_SECONDS = 6 * 60 * 60


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
# transcript. Used by the STOP_HOOK strategy.
_TURN_COMPLETE_SOURCE = "mngr/turn_complete"
_TURN_END_EVENT_TYPE = "turn_end"

# How long to wait, after the turn-end signal fires, for the
# assistant_message event to show up in the common transcript. The
# converters write `events/<source>/common_transcript/events.jsonl` on a
# ~5s timer, while our turn-end signal can fire sooner. Without a wait
# here, a fast turn could be detected as done before the conversion sees
# the assistant_message and we'd return empty text.
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


def extract_assistant_text(event: Dict[str, Any]) -> Optional[str]:
    """Return an assistant_message's text content, or None if absent.

    Used to concatenate the agent's final response from the common
    transcript. The common-transcript converters for both mngr_claude and
    mngr_antigravity normalize to the same `assistant_message` shape, so
    one extractor serves both.
    """
    if event.get("type") != "assistant_message":
        return None
    text = event.get("text")
    if isinstance(text, str) and text:
        return text
    return None


def extract_status(event: Dict[str, Any]) -> Optional[str]:
    """Return a short status line for the dashboard, or None if irrelevant.

    Prefers the assistant_message text when present (whitespace-collapsed);
    falls back to the first tool_call name when the message carries no text
    (e.g. agy's PLANNER_RESPONSE for a tool-use step has empty text and
    only tool_calls; claude can produce the same shape when it calls a
    tool with no preamble). The fallback gives the dashboard a live
    "Running <tool>" status during tool runs.
    """
    if event.get("type") != "assistant_message":
        return None
    text = event.get("text")
    if isinstance(text, str) and text.strip():
        return " ".join(text.split())
    for call in event.get("tool_calls", []) or []:
        tool_name = call.get("tool_name")
        if isinstance(tool_name, str) and tool_name:
            return f"Running {tool_name}"
    return None


def _generate_agent_name(task_id: str, stage: str) -> str:
    short_task = task_id.split("_")[-1][:8] if "_" in task_id else task_id[:8]
    safe_stage = re.sub(r"[^a-z0-9-]", "-", stage.lower())[:32].strip("-") or "step"
    suffix = secrets.token_hex(3)
    return f"cata-{short_task}-{safe_stage}-{suffix}"


@dataclass(eq=False, repr=False)
class MngrAgentRunner(AgentRunner):
    """Drives an mngr-managed interactive agent for a single Catalyst step.

    Lifecycle per `run()` call:
        1. mngr create --no-connect ...    (returns once agent is spawned)
        2. mngr event --follow             (background, status + STOP_HOOK
                                            turn-end detection)
        3. mngr wait --state WAITING       (only for WAITING_STATE strategy)
           or wait for turn_end event      (STOP_HOOK strategy)
        4. mngr stop                       (halts cleanly; transcript preserved)

    Stopped agents stay visible in `mngr list` for `mngr connect` /
    `mngr transcript` post-mortem; explicit cleanup via `mngr destroy` is
    a separate user-invoked path.
    """

    # CLI agent type passed to `mngr create --type ...` (e.g. "claude",
    # "antigravity").
    agent_type: str
    # User-facing framework string the orchestrator/dashboard use (e.g.
    # "mngr-claude").
    framework: str
    # `events/<source>/common_transcript/events.jsonl` is read for harvest
    # + status. Per-agent-type because each plugin writes to its own
    # source (mngr_claude -> "claude/common_transcript",
    # mngr_antigravity -> "antigravity/common_transcript").
    transcript_source: str
    # Strategy for detecting "this turn finished" -- see TurnCompletion.
    turn_completion: TurnCompletion
    # Static CLI args appended after `--` on every `mngr create`. Use this
    # for flags the agent always wants (e.g. agy's "--sandbox").
    agent_args: Tuple[str, ...] = ()
    # If set, `[model_flag, model]` is appended to agent_args whenever the
    # caller passes a model. Agents that have no model selection (agy)
    # leave this None.
    model_flag: Optional[str] = None
    # Per-agent-type env vars layered on top of the shared set built in
    # `run()` (UV_CACHE_DIR, CATALYST_DB_PATH, MPLCONFIGDIR).
    extra_env: Dict[str, str] = field(default_factory=dict)

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

    def _build_agent_args(self, model: Optional[str]) -> List[str]:
        args = list(self.agent_args)
        if model and self.model_flag:
            args.extend([self.model_flag, model])
        return args

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
        env_vars.update(self.extra_env)
        if tx_id:
            env_vars["CONTEXT_TRANSACTION_ID"] = tx_id

        labels = {
            "app": "catalyst",
            "catalyst-task": task_id,
            "catalyst-stage": resolved_stage,
            "catalyst-framework": self.framework,
        }

        # `prompt_file` is created inside the try so that a failure to
        # create the tempfile (disk full, EROFS, etc.) is converted to
        # the runner's structured `(None, agent_name, error)` return
        # instead of an unhandled exception. The `finally` below guards
        # `prompt_file is not None` so the cleanup never raises
        # UnboundLocalError on that failure path.
        prompt_file = None
        try:
            prompt_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, prefix=f"{agent_name}-"
            )
            prompt_file.write(prompt)
            prompt_file.close()

            create_cmd = [
                "mngr",
                "create",
                agent_name,
                "--type",
                self.agent_type,
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

            agent_args = self._build_agent_args(model)
            if agent_args:
                create_cmd.append("--")
                create_cmd.extend(agent_args)

            logger.debug(
                f"[AGENT] [{task_id[:8]}] {self.framework} via mngr: {shlex.join(create_cmd)}"
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
            return None, agent_name, f"{self.framework} execution error: {e}"

        finally:
            if prompt_file is not None:
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
        """Wait for the turn to end, then parse the final assistant text."""
        del task_id  # only used for log prefix today; kept on the signature for future use
        saw_turn_end = self._wait_for_turn_end(agent_name, on_status)
        if not saw_turn_end:
            return (None, agent_name, self._no_completion_error())

        assistant_text = self._read_assistant_text(agent_name, on_status)

        data = parse_json_result(assistant_text)
        if data:
            return data, agent_name, None

        return (
            None,
            agent_name,
            f"Could not parse JSON output from {self.framework} result. Preview: {assistant_text[:800]}...",
        )

    def _no_completion_error(self) -> str:
        """Error string when the turn never completed. Phrased per the
        turn-completion strategy so the message points at the actual
        failure mode rather than a generic one."""
        if self.turn_completion is TurnCompletion.WAITING_STATE:
            return (
                f"Agent never reached the WAITING lifecycle state "
                f"(deadline was {_WAIT_TIMEOUT_SECONDS}s). {self.framework} "
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

        Three concurrent watchers feed a shared `done` event; whichever
        fires first wins:

        * `mngr event --follow` -- streams transcript events. Always
          consumed for `on_status` updates; for STOP_HOOK it also sets
          `saw_turn_end` on a `mngr/turn_complete` `turn_end` event.
        * `mngr wait --state STOPPED` -- catches external pause / cancel
          (server.py calls `mngr stop` via `cancel_task_process`).
        * `mngr wait --state WAITING` -- only spawned for WAITING_STATE;
          sets `saw_turn_end` when the agent's per-task active marker is
          cleared by the plugin's Stop hook.

        Returns True iff a turn-end signal was seen. False covers both
        the deadline expiring and an external stop; the orchestrator
        distinguishes by checking the task's status after run() returns.
        """
        deadline = time.monotonic() + _WAIT_TIMEOUT_SECONDS
        saw_turn_end = threading.Event()
        done = threading.Event()

        event_proc = subprocess.Popen(
            ["mngr", "event", agent_name, "--follow", "--format", "jsonl"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        stop_proc = self._spawn_wait_for_state(agent_name, "STOPPED")
        wait_proc = (
            self._spawn_wait_for_state(agent_name, "WAITING")
            if self.turn_completion is TurnCompletion.WAITING_STATE
            else None
        )

        threads: List[threading.Thread] = [
            threading.Thread(
                target=self._consume_events,
                args=(event_proc, on_status, saw_turn_end, done),
                daemon=True,
            ),
            threading.Thread(
                target=self._watch_proc,
                args=(stop_proc, done, None),
                daemon=True,
            ),
        ]
        if wait_proc is not None:
            threads.append(
                threading.Thread(
                    target=self._watch_proc,
                    args=(wait_proc, done, saw_turn_end),
                    daemon=True,
                )
            )

        for t in threads:
            t.start()

        try:
            remaining = max(0.0, deadline - time.monotonic())
            done.wait(timeout=remaining)
        finally:
            for proc in (event_proc, stop_proc, wait_proc):
                if proc is not None:
                    self._terminate_proc(proc)
            for t in threads:
                t.join(timeout=5)
        return saw_turn_end.is_set()

    @staticmethod
    def _spawn_wait_for_state(agent_name: str, state: str) -> subprocess.Popen:
        return subprocess.Popen(
            [
                "mngr",
                "wait",
                agent_name,
                "--state",
                state,
                "--timeout",
                f"{_WAIT_TIMEOUT_SECONDS}s",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def _watch_proc(
        proc: subprocess.Popen,
        done: threading.Event,
        success_event: Optional[threading.Event],
    ) -> None:
        """Wait for `proc` to exit, then set `done`. If `success_event` is
        given, also set it when `proc` exited 0 (used by the WAITING
        watcher to signal "turn ended cleanly")."""
        rc = proc.wait()
        if success_event is not None and rc == 0:
            success_event.set()
        done.set()

    def _consume_events(
        self,
        event_proc: subprocess.Popen,
        on_status: Optional[Callable[[str], None]],
        saw_turn_end: threading.Event,
        done: threading.Event,
    ) -> None:
        """Read `event_proc`'s stdout line-by-line, dispatching events to
        the status callback and (for STOP_HOOK) checking for the turn_end
        signal."""
        assert event_proc.stdout is not None
        for line in event_proc.stdout:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if on_status:
                status = extract_status(event)
                if status:
                    try:
                        on_status(status)
                    except Exception as cb_err:
                        logger.error(f"[AGENT] on_status error: {cb_err}")
            if (
                self.turn_completion is TurnCompletion.STOP_HOOK
                and event.get("source") == _TURN_COMPLETE_SOURCE
                and event.get("type") == _TURN_END_EVENT_TYPE
            ):
                saw_turn_end.set()
                done.set()
                return

    @staticmethod
    def _terminate_proc(proc: subprocess.Popen) -> None:
        """Best-effort terminate -> wait -> kill of a helper subprocess.
        Same shape as mngr's own RunningProcess.terminate: SIGTERM, give
        it 5s, SIGKILL on timeout."""
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

    def _read_transcript_events(self, agent_name: str) -> List[Dict[str, Any]]:
        """Read the agent's common transcript as a list of parsed events,
        in file order. Returns [] if the source has no events yet."""
        result = subprocess.run(
            [
                "mngr",
                "event",
                agent_name,
                "--source",
                self.transcript_source,
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
        converters write `events/<source>/common_transcript/events.jsonl`
        on a ~5s timer, while our turn-end signal can fire sooner. Without
        a wait here, a fast turn could be detected as done before the
        conversion sees the assistant_message and we'd return empty text.

        If `on_status` is given, fire a status callback for every event
        as a backstop -- a fast turn can finish before the live follower
        in `_wait_for_turn_end` ever sees the assistant_message event.
        Driving on_status here guarantees the dashboard's last_status
        field reflects the final output even in that race.
        """
        deadline = time.monotonic() + _POST_TURN_END_POLL_SECONDS
        seen_event_ids: set[str] = set()
        while True:
            parts: List[str] = []
            for event in self._read_transcript_events(agent_name):
                text = extract_assistant_text(event)
                if text:
                    parts.append(text)
                if on_status:
                    event_id = event.get("event_id")
                    if event_id and event_id not in seen_event_ids:
                        seen_event_ids.add(event_id)
                        status = extract_status(event)
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
