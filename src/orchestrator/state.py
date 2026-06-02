import json
import os
import signal
import subprocess
import threading
import time
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, TypeAlias, Union
from .models import Task, TasksState, TaskStatus, StepStatus
from .utils import get_catalyst_path

logger = logging.getLogger(__name__)


def _get_state_file() -> str:
    path = os.path.join(get_catalyst_path(), "tasks_state.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


_lock = threading.Lock()
_task_locks: Dict[str, threading.Lock] = {}


# Cancellable work for each Catalyst task. The two variants are exclusive
# wrappers so dispatch in `cancel_task_process` is a plain isinstance check
# against a tagged type, not a guess about the underlying object.
@dataclass(frozen=True)
class _DirectSubprocess:
    """A direct CLI subprocess (`claude` / `gemini` / `agy`) registered by
    cli_base.py; cancelled via SIGTERM -> SIGKILL on its process group."""
    process: subprocess.Popen


@dataclass(frozen=True)
class _MngrAgent:
    """An mngr-managed agent registered by mngr_runner.py; cancelled by
    shelling out to `mngr stop <agent_name>`."""
    agent_name: str


_RunningEntry: TypeAlias = Union[_DirectSubprocess, _MngrAgent]
_running: Dict[str, List[_RunningEntry]] = {}

_state_cache: Optional[TasksState] = None


def get_task_lock(task_id: str) -> threading.Lock:
    with _lock:
        if task_id not in _task_locks:
            _task_locks[task_id] = threading.Lock()
        return _task_locks[task_id]


def register_process(task_id: str, process: subprocess.Popen):
    """Direct runners: track a `claude` / `gemini` / `agy` subprocess."""
    with _lock:
        _running.setdefault(task_id, []).append(_DirectSubprocess(process))


def unregister_process(task_id: str, process: subprocess.Popen):
    _remove_entry(task_id, _DirectSubprocess(process))


def register_agent(task_id: str, agent_name: str) -> None:
    """Mngr runners: track a `mngr create`-spawned agent by name."""
    entry = _MngrAgent(agent_name)
    with _lock:
        entries = _running.setdefault(task_id, [])
        if entry not in entries:
            entries.append(entry)


def unregister_agent(task_id: str, agent_name: str) -> None:
    _remove_entry(task_id, _MngrAgent(agent_name))


def _remove_entry(task_id: str, entry: _RunningEntry) -> None:
    with _lock:
        entries = _running.get(task_id)
        if not entries:
            return
        try:
            entries.remove(entry)
        except ValueError:
            pass
        if not entries:
            del _running[task_id]


def cancel_task_process(task_id: str, timeout: int = 30) -> None:
    """Cancel everything `task_id` registered: direct subprocesses get
    SIGTERM (then SIGKILL after `timeout`); mngr agents get `mngr stop`."""
    with _lock:
        entries = list(_running.get(task_id, ()))

    if not entries:
        return

    processes_to_cancel = [e.process for e in entries if isinstance(e, _DirectSubprocess)]
    agents_to_stop = [e.agent_name for e in entries if isinstance(e, _MngrAgent)]

    if processes_to_cancel:
        logger.info(
            f"[PROCESS] Stopping {len(processes_to_cancel)} subprocess(es) for task {task_id[:8]}"
        )
        for proc in processes_to_cancel:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception as e:
                logger.error(f"[PROCESS] Failed to SIGTERM group for pid {proc.pid}: {e}")

        deadline = time.time() + timeout
        for proc in processes_to_cancel:
            remaining = max(0, deadline - time.time())
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"[PROCESS] PID {proc.pid} didn't exit after {timeout}s, sending SIGKILL to group"
                )
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    proc.wait(timeout=5)
                except Exception as e:
                    logger.error(
                        f"[PROCESS] Failed to SIGKILL group for pid {proc.pid}: {e}"
                    )
            except Exception:
                pass

    if agents_to_stop:
        logger.info(
            f"[PROCESS] Stopping {len(agents_to_stop)} mngr agent(s) for task {task_id[:8]}"
        )
        for agent_name in agents_to_stop:
            try:
                subprocess.run(
                    ["mngr", "stop", agent_name],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"[PROCESS] mngr stop {agent_name} timed out after {timeout}s"
                )
            except Exception as e:
                logger.error(f"[PROCESS] mngr stop {agent_name} failed: {e}")

    with _lock:
        _running.pop(task_id, None)


_last_written_json: Optional[str] = None


def _load_state() -> TasksState:
    global _state_cache, _last_written_json
    if _state_cache is not None:
        return _state_cache

    if not os.path.exists(_get_state_file()):
        _state_cache = TasksState(tasks=[])
        _last_written_json = json.dumps(_state_cache.model_dump(), indent=2)
        return _state_cache
    try:
        with open(_get_state_file(), "r") as f:
            content = f.read()
            _last_written_json = content
            data = json.loads(content)
            _state_cache = TasksState.model_validate(data)
            return _state_cache
    except Exception:
        _state_cache = TasksState(tasks=[])
        _last_written_json = json.dumps(_state_cache.model_dump(), indent=2)
        return _state_cache


def _save_state(state: TasksState, disk_save: bool = True):
    global _state_cache, _last_written_json
    _state_cache = state

    if not disk_save:
        return

    # Strip transient fields like last_status before saving to disk
    data = state.model_dump()
    for task in data.get("tasks", []):
        for step in task.get("steps", []):
            if "last_status" in step:
                step["last_status"] = None

    json_str = json.dumps(data, indent=2)

    # Skip disk write if nothing actually changed
    if _last_written_json == json_str:
        return

    if os.path.exists(_get_state_file()):
        try:
            os.replace(_get_state_file(), f"{_get_state_file()}.bak")
        except Exception as e:
            logger.warning(f"Could not create backup of state file: {e}")

    with open(_get_state_file(), "w") as f:
        f.write(json_str)

    _last_written_json = json_str


def get_tasks() -> List[Task]:
    with _lock:
        return _load_state().tasks


def get_task(task_id: str) -> Optional[Task]:
    with _lock:
        state = _load_state()
        for task in state.tasks:
            if task.id == task_id:
                return task
    return None


def add_task(task: Task):
    with _lock:
        state = _load_state()
        state.tasks.append(task)
        _save_state(state)


def update_task(task: Task):
    # Sanity check: ensure step stages are unique
    stages = [s.stage for s in task.steps]
    if len(stages) != len(set(stages)):
        raise ValueError(f"Duplicate step stages detected in task {task.id}: {stages}")

    with _lock:
        state = _load_state()

        for i, old_t in enumerate(state.tasks):
            if old_t.id == task.id:
                state.tasks[i] = task
                break

        _save_state(state, disk_save=True)


def initialize_state():
    with _lock:
        state = _load_state()
        modified = False

        # Local import to avoid circular dependency
        from .workflows import get_workflow
        from .orchestrator import get_full_structure

        for task in state.tasks:
            # Always ensure structure is up-to-date with current steps
            workflow = get_workflow(task.workflow_name)
            if workflow:
                new_struct = get_full_structure(workflow, task)
                if new_struct != task.workflow_structure:
                    task.workflow_structure = new_struct
                    modified = True

            if task.status == TaskStatus.RUNNING or task.status == TaskStatus.PENDING:
                task.status = TaskStatus.PAUSED
                modified = True
            for step in task.steps:
                if step.status in (StepStatus.RUNNING, StepStatus.WAITING):
                    step.status = StepStatus.PAUSED
                    modified = True
        if modified:
            _save_state(state)


def delete_task(task_id: str):
    cancel_task_process(task_id)

    with _lock:
        state = _load_state()
        state.tasks = [t for t in state.tasks if t.id != task_id]
        _save_state(state)
        if task_id in _task_locks:
            del _task_locks[task_id]


def shutdown_all():
    """Stop all running agents (direct + mngr) and mark tasks as PAUSED."""
    with _lock:
        task_ids = list(_running.keys())

        # Also mark all tasks as PAUSED so they don't look like they failed
        state = _load_state()
        modified = False
        for task in state.tasks:
            if task.status == TaskStatus.RUNNING or task.status == TaskStatus.PENDING:
                task.status = TaskStatus.PAUSED
                modified = True
            for step in task.steps:
                if step.status in (StepStatus.RUNNING, StepStatus.WAITING):
                    step.status = StepStatus.PAUSED
                    modified = True
        if modified:
            _save_state(state)

    if task_ids:
        logger.info(
            f"[SHUTDOWN] Stopping mngr agents for {len(task_ids)} tasks..."
        )
        for tid in task_ids:
            cancel_task_process(tid)
