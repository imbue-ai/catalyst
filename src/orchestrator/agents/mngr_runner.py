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
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from .base import AgentRunner, parse_json_result
from ..state import Cancellable, register_cancellable, unregister_cancellable

logger = logging.getLogger(__name__)


# How long the runner may block waiting for a turn to finish (seconds).
# Multi-skill cascades (e.g. `/swarm` spawning Task subagents) can run
# for hours; this cap is generous on purpose. Matches the timeout the
# direct Antigravity CLI runner uses. The agent's tmux session is the
# source of cost, not this timeout.
_WAIT_TIMEOUT_SECONDS = 6 * 60 * 60


# After the turn-end (WAITING) signal fires, wait for the step's expected JSON
# to appear in the harvested assistant text. The wait is *state-aware* (see
# `_await_final_message`): the WAITING grace clock below bounds how long we sit
# in a *single, continuous* WAITING stretch without parseable text before
# giving up. If the agent leaves WAITING (resumes RUNNING) the clock resets and
# we wait for the next WAITING, so a genuinely long continuation is never
# truncated. The poll interval is how often we re-check the agent's lifecycle
# state and the harvested text.
#
# Why a grace at all, given the agent reaches WAITING? Two reasons it can be
# WAITING with no parseable text yet:
#   1. Converter lag. The transcript converters write
#      `events/<source>/common_transcript/events.jsonl`, and historically did
#      so on a ~5s timer that our turn-end signal could outrun. Current mngr
#      closes this at the source: the agent's turn-end hook
#      (`wait_for_stop_hook.sh` for claude, `statusline.sh` for agy) runs a
#      synchronous `--single-pass` of the converters *before* clearing the
#      `active` marker that signals WAITING, so the common transcript already
#      reflects the final message by the time we observe WAITING (modulo the
#      brief in-flight lag of `mngr event --follow` delivering the line to us).
#      The grace is the fallback for an mngr build without that flush.
#   2. The agent genuinely ended its turn on non-JSON output. Rare for Catalyst
#      (steps are contracted to emit final JSON); the grace elapses and the
#      step then fails on the parse, as it should.
_POST_TURN_END_GRACE_SECONDS = 30.0
_POST_TURN_END_POLL_INTERVAL = 2.0

# mngr `AgentLifecycleState` values we key on while harvesting the final
# message. WAITING is the turn-end signal; the RUNNING-ish states mean the turn
# is still in progress (so keep waiting); anything else is terminal.
_AGENT_STATE_WAITING = "WAITING"
_RESUMABLE_RUNNING_STATES = frozenset({"RUNNING", "RUNNING_UNKNOWN_AGENT_TYPE"})

# FIXME(turn-end-grace): incomplete fix for premature turn-end detection.
#
# mngr signals "turn ended" off a single Claude Code `Stop`/`end_turn`, but a
# single Catalyst step (notably the `/swarm` cascade) can emit more than one
# `end_turn` -- e.g. the model announces "I'll spawn N agents and wait" as its
# own response before producing the real final message. When that happens the
# parent briefly goes WAITING, then resumes. This is intermittent (~3% on
# `/swarm`) and is not unique to detecting turn end via WAITING: the Stop-hook
# `turn_complete` event approach this replaced keyed off the same `Stop`, so it
# was affected too (analytically more so -- it reacted to the emitted event
# immediately, while WAITING waits out `wait_for_stop_hook.sh`'s grace).
#
# `_await_final_message` handles the *common* shape of this: it watches the
# lifecycle state, so a premature WAITING that resumes to RUNNING is waited
# through (we re-arm on the next WAITING) and only a parseable message while
# WAITING -- or a continuous-WAITING timeout / terminal state -- ends the wait.
#
# Why it is still not a clean fix: if the model genuinely ends its turn early
# on non-JSON output and emits nothing further, the agent stays WAITING, the
# grace elapses, and the step still fails (just later). And if a RUNNING blip
# between two intermediate WAITINGs is shorter than one poll interval we can
# miss it -- we then don't reset the continuous-WAITING grace clock, so a turn
# that is in fact still progressing could be cut off once the grace elapses. A
# real fix needs mngr to distinguish an intermediate `end_turn` from the true
# turn end (e.g. a turn-aware marker).

# Catalyst's isolated `mngr` host_dir, kept separate from the user's main
# `~/.mngr` so Catalyst's agents don't mix in and the runner's `mngr` calls
# aren't blocked by stale fields in the user's profile settings (e.g.
# `plugins.kanpan.column_order`).
# If you change this, also update claude_skills/settings.json's sandbox
# `filesystem.allowWrite` to match: the mngr_claude plugin's readiness hooks
# write the per-agent `active` marker under this path, and that marker is what
# `mngr wait --state WAITING` (our turn-end signal) reads.
MNGR_HOST_DIR = os.path.expanduser("~/.mngr-catalyst")


def mngr_env() -> dict[str, str]:
    env = os.environ.copy()
    env["MNGR_HOST_DIR"] = MNGR_HOST_DIR
    return env


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
        2. mngr event --follow             (background, status + final
                                            assistant-text harvest)
        3. mngr wait --state WAITING       (turn-end signal)
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
    # Static CLI args appended after `--` on every `mngr create`. Use this
    # for flags the agent always wants (e.g. agy's "--sandbox").
    agent_args: Tuple[str, ...] = ()
    # If set, `[model_flag, model]` is appended to agent_args whenever the
    # caller passes a model. Agents that have no model selection (agy)
    # leave this None.
    model_flag: Optional[str] = None
    # If set, `[effort_flag, effort]` is appended to agent_args whenever the
    # caller passes an effort. Agents that have no effort selection
    # leave this None.
    effort_flag: Optional[str] = None
    # Per-agent-type env vars layered on top of the shared set built in
    # `run()` (UV_CACHE_DIR, CATALYST_DB_PATH, MPLCONFIGDIR).
    extra_env: Dict[str, str] = field(default_factory=dict)

    @contextlib.contextmanager
    def _registered_agent(
        self, task_id: str, agent_name: str
    ) -> Generator[None, None, None]:
        """Scope a registered agent to a `with` block: register on entry,
        always stop + unregister on exit. Used to centralize the
        "best-effort halt this agent no matter how we exit" pattern so
        every terminal path -- success, wait timeout, wait failure, or
        unexpected exception -- gets the same cleanup. `_stop_agent`
        already swallows and logs subprocess errors; we add an extra
        guard here so a stop failure can't mask the original exception
        when one is in flight.
        """
        cancellable = Cancellable(
            description=f"mngr agent {agent_name}",
            cancel=lambda timeout: self._stop_agent(
                agent_name, task_id, timeout=timeout
            ),
        )
        register_cancellable(task_id, cancellable)
        try:
            yield
        finally:
            # Bound the cleanup-path stop so a hung `mngr stop` can't pin
            # this thread forever. Matches `cancel_task_process`'s default
            # timeout in `state.py`; `_stop_agent` already converts a
            # `TimeoutExpired` into a logged warning and returns.
            try:
                self._stop_agent(agent_name, task_id, timeout=30)
            except Exception as stop_err:
                logger.warning(
                    f"[AGENT] [{task_id[:8]}] failed to stop {agent_name} on exit: {stop_err}"
                )
            unregister_cancellable(task_id, cancellable)

    def _build_agent_args(self, model: Optional[str], effort: Optional[str] = None) -> List[str]:
        args = list(self.agent_args)
        if model and self.model_flag:
            args.extend([self.model_flag, model])
        if effort and self.effort_flag:
            args.extend([self.effort_flag, effort])
        return args

    def run(
        self,
        task_id: str,
        prompt: str,
        env_folder: str,
        stage: str,
        common_environment_variables: Dict[str, str],
        model: Optional[str] = None,
        effort: Optional[str] = None,
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        abs_env_folder = os.path.abspath(env_folder)
        # One fallback for both the agent name and the label, so a user
        # filtering `mngr list` by catalyst-stage gets the same value
        # they see in the agent name.
        resolved_stage = stage or "step"
        agent_name = _generate_agent_name(task_id, resolved_stage)

        env_vars = common_environment_variables.copy()
        env_vars.update(self.extra_env)

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

            agent_args = self._build_agent_args(model, effort)
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
                    env=mngr_env(),
                )
            except FileNotFoundError as e:
                return None, None, f"mngr CLI not found on PATH: {e}"

            if create_result.returncode != 0:
                combined = (
                    (create_result.stderr or "") + "\n" + (create_result.stdout or "")
                )
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
                # Close before unlink so a failure between `NamedTemporaryFile(...)`
                # and the explicit `close()` above (e.g. `.write()` raising on a
                # full disk) doesn't leak the fd. close() is a no-op on an
                # already-closed wrapper, so the success path is unchanged.
                try:
                    prompt_file.close()
                except Exception:
                    pass
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
        del (
            task_id
        )  # only used for log prefix today; kept on the signature for future use
        saw_turn_end, assistant_text = self._wait_for_turn_end(agent_name, on_status)
        if not saw_turn_end:
            return (None, agent_name, self._no_completion_error())

        data = parse_json_result(assistant_text)
        if data:
            return data, agent_name, None

        if not assistant_text:
            # Distinguish "agent emitted nothing we could harvest" from
            # "agent emitted unparseable text" -- they imply different
            # debugging paths (transcript converter lag / agent never
            # produced a final message vs. wrong skill output shape).
            return (
                None,
                agent_name,
                f"No assistant_message text found in {self.framework} "
                "transcript after turn_end. The common-transcript "
                "converter may not have caught up, or the agent did not "
                "emit a final message.",
            )

        return (
            None,
            agent_name,
            f"Could not parse JSON output from {self.framework} result. Preview: {assistant_text[:800]}...",
        )

    def _no_completion_error(self) -> str:
        """Error string when the turn never completed. `_wait_for_turn_end`
        returns False both on actual deadline expiry AND on an external
        `mngr stop` arriving (server.py pause), so the wording must not
        present the deadline as the *only* explanation."""
        return (
            f"Agent stopped without reaching the WAITING lifecycle state. "
            f"{self.framework} completion is signalled when the agent's "
            "per-task active marker is cleared; this can happen if the "
            "agent was paused / stopped externally, the plugin's hooks "
            "didn't fire, or the wait cap "
            f"({_WAIT_TIMEOUT_SECONDS}s) elapsed before completion."
        )

    def _wait_for_turn_end(
        self,
        agent_name: str,
        on_status: Optional[Callable[[str], None]],
    ) -> Tuple[bool, Optional[str]]:
        """Block until the agent's turn finishes (or it is stopped).

        Three concurrent watchers feed a shared `watch_done` event; whichever
        fires first wins:

        * `mngr event --follow` -- streams transcript events; consumed for
          `on_status` updates and to harvest the final assistant text.
        * `mngr wait --state STOPPED` -- catches external pause / cancel
          (server.py calls `mngr stop` via `cancel_task_process`).
        * `mngr wait --state WAITING` -- sets `saw_turn_end` when the agent's
          per-task active marker is cleared by the plugin's Stop hook
          (the turn-end signal).

        Returns (saw_turn_end, last_assistant_text).
        """
        deadline = time.monotonic() + _WAIT_TIMEOUT_SECONDS
        saw_turn_end = threading.Event()
        watch_done = threading.Event()

        state = {"last_assistant_text": None}

        # Initialize before the spawns so the `finally` always sees them.
        # If a Popen partway through raises (transient fork/OS error, mngr
        # CLI yanked mid-task), this guarantees any earlier-spawned helper
        # subprocess still gets terminated rather than leaked.
        event_proc: Optional[subprocess.Popen] = None
        stop_proc: Optional[subprocess.Popen] = None
        wait_proc: Optional[subprocess.Popen] = None
        threads: List[threading.Thread] = []

        try:
            event_proc = subprocess.Popen(
                ["mngr", "event", agent_name, "--follow", "--format", "jsonl"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=mngr_env(),
            )
            stop_proc = self._spawn_wait_for_state(agent_name, "STOPPED")
            wait_proc = self._spawn_wait_for_state(agent_name, "WAITING")

            threads.append(
                threading.Thread(
                    target=self._consume_events,
                    args=(event_proc, on_status, state),
                    daemon=True,
                )
            )
            threads.append(
                threading.Thread(
                    target=self._watch_proc,
                    args=(stop_proc, watch_done, None),
                    daemon=True,
                )
            )
            threads.append(
                threading.Thread(
                    target=self._watch_proc,
                    args=(wait_proc, watch_done, saw_turn_end),
                    daemon=True,
                )
            )

            for t in threads:
                t.start()

            remaining = max(0.0, deadline - time.monotonic())
            watch_done.wait(timeout=remaining)

            # After the turn-end signal, wait (state-aware) for the step's final
            # parseable message: `_consume_events` keeps updating
            # state["last_assistant_text"] until we terminate it in the finally
            # below. Only meaningful once a turn-end was actually observed; an
            # external stop leaves saw_turn_end unset and needs no grace.
            if saw_turn_end.is_set():
                self._await_final_message(agent_name, state, deadline)
        finally:
            for proc in (event_proc, stop_proc, wait_proc):
                if proc is not None:
                    self._terminate_proc(proc)
            for t in threads:
                t.join(timeout=5)
        return saw_turn_end.is_set(), state["last_assistant_text"]

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
            env=mngr_env(),
        )

    @staticmethod
    def _poll_lifecycle_state(agent_name: str) -> Optional[str]:
        """Return the agent's current mngr lifecycle state (e.g. "WAITING",
        "RUNNING", "STOPPED"), or None if it can't be determined. A single-shot
        `mngr list` read against Catalyst's isolated host dir; mngr's own state
        rules decide the value, so we don't re-derive it here."""
        result = subprocess.run(
            ["mngr", "list", "--include", f'name == "{agent_name}"', "--format", "jsonl"],
            check=False,
            capture_output=True,
            text=True,
            env=mngr_env(),
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("name") == agent_name:
                value = entry.get("state")
                return value if isinstance(value, str) else None
        return None

    def _await_final_message(
        self,
        agent_name: str,
        state: Dict[str, Any],
        deadline: float,
    ) -> None:
        """Wait, state-awarely, for the step's parseable final message after the
        turn-end (WAITING) signal. Returns (leaving the harvested text in
        `state["last_assistant_text"]`) once any of these holds, or the outer
        `deadline` passes:

          * the harvested text parses as JSON while the agent is WAITING -- the
            real end of the turn (the common case, after the first poll);
          * the agent has been *continuously* WAITING for
            `_POST_TURN_END_GRACE_SECONDS` with no parseable text -- converter-lag
            fallback, or it genuinely ended on non-JSON output;
          * the agent reaches a terminal state (e.g. STOPPED via external pause).

        While the agent is RUNNING -- e.g. it emitted a premature/intermediate
        `end_turn`, briefly went WAITING, then resumed (`/swarm`) -- we keep
        waiting and re-arm on the next WAITING. An outer loop blocks on the next
        WAITING (cheap while RUNNING); an inner loop polls during each WAITING
        stretch. See the `_POST_TURN_END_GRACE_SECONDS` FIXME."""
        while time.monotonic() < deadline:
            if self._poll_waiting_window(agent_name, state, deadline) != "resumed":
                return
            # Resumed to RUNNING: block until the next WAITING (the possibly-real
            # turn end) or a terminal state, then re-enter the inner poll.
            if not self._block_until_waiting(agent_name, deadline):
                return

    def _poll_waiting_window(
        self,
        agent_name: str,
        state: Dict[str, Any],
        deadline: float,
    ) -> str:
        """Poll a single continuous WAITING stretch. Returns "resumed" if the
        agent left WAITING for a RUNNING state (caller should re-arm on the next
        WAITING), or "done" if the wait is over for any other reason (parsed,
        grace elapsed, terminal state, or `deadline`)."""
        grace_deadline = min(deadline, time.monotonic() + _POST_TURN_END_GRACE_SECONDS)
        while time.monotonic() < deadline:
            lifecycle = self._poll_lifecycle_state(agent_name)
            if lifecycle in _RESUMABLE_RUNNING_STATES:
                return "resumed"
            if lifecycle != _AGENT_STATE_WAITING:
                return "done"  # terminal (stopped/done/unknown) -- nothing more is coming
            if parse_json_result(state["last_assistant_text"]) is not None:
                return "done"  # WAITING && parses -- the real end
            if time.monotonic() >= grace_deadline:
                return "done"  # continuously WAITING past the grace without parseable text
            time.sleep(_POST_TURN_END_POLL_INTERVAL)
        return "done"

    def _block_until_waiting(self, agent_name: str, deadline: float) -> bool:
        """Block until the agent returns to WAITING (the next turn end), bounded
        by `deadline`. Also targets STOPPED so an external pause mid-continuation
        can't strand us blocking for the full deadline. Returns True iff the
        agent is WAITING when the wait resolves."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        proc = subprocess.Popen(
            [
                "mngr",
                "wait",
                agent_name,
                "--state",
                _AGENT_STATE_WAITING,
                "--state",
                "STOPPED",
                "--timeout",
                f"{int(remaining)}s",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=mngr_env(),
        )
        try:
            rc = proc.wait()
        finally:
            self._terminate_proc(proc)
        if rc != 0:
            return False  # timed out / errored before reaching either state
        return self._poll_lifecycle_state(agent_name) == _AGENT_STATE_WAITING

    @staticmethod
    def _watch_proc(
        proc: subprocess.Popen,
        watch_done: threading.Event,
        success_event: Optional[threading.Event],
    ) -> None:
        """Wait for `proc` to exit, then set `watch_done`. If `success_event` is
        given, also set it when `proc` exited 0 (used by the WAITING
        watcher to signal "turn ended cleanly")."""
        rc = proc.wait()
        if success_event is not None and rc == 0:
            success_event.set()
        watch_done.set()

    def _consume_events(
        self,
        event_proc: subprocess.Popen,
        on_status: Optional[Callable[[str], None]],
        state: Dict[str, Any],
    ) -> None:
        """Read `event_proc`'s stdout line-by-line, dispatching events to
        the status callback and harvesting the latest assistant text. Runs
        until `event_proc` is terminated by `_wait_for_turn_end`; the
        turn-end signal itself comes from the WAITING watcher, not here."""
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

            if event.get("source") == self.transcript_source:
                text = extract_assistant_text(event)
                if text is not None:
                    state["last_assistant_text"] = text

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

    def _stop_agent(
        self, agent_name: str, task_id: str, timeout: Optional[float] = None
    ) -> None:
        try:
            result = subprocess.run(
                ["mngr", "stop", agent_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=mngr_env(),
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                f"[AGENT] [{task_id[:8]}] mngr stop {agent_name} timed out after {timeout}s"
            )
            return
        if result.returncode != 0:
            logger.warning(
                f"[AGENT] [{task_id[:8]}] mngr stop {agent_name} failed: "
                f"{(result.stderr or result.stdout)[:300]}"
            )
