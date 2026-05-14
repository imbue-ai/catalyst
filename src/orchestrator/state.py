import json
import os
import subprocess
import threading
import logging
from typing import Dict, List, Optional, Set
from .models import Task, TasksState, TaskStatus, StepStatus
from .utils import get_ai_scientist_path

logger = logging.getLogger(__name__)


def _get_state_file() -> str:
    path = os.path.join(get_ai_scientist_path(), "tasks_state.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


_lock = threading.Lock()
_task_locks: Dict[str, threading.Lock] = {}
# Mngr agent names that are currently RUNNING for each ai-scientist task.
# `cancel_task_process` shells out to `mngr stop` for each. Stopped agents
# stay in `mngr list` so users can `mngr connect` / `mngr transcript` them
# post-mortem; explicit cleanup is via `mngr destroy` (not from the cancel
# path).
_running_agents: Dict[str, Set[str]] = {}

_state_cache: Optional[TasksState] = None


def get_task_lock(task_id: str) -> threading.Lock:
    with _lock:
        if task_id not in _task_locks:
            _task_locks[task_id] = threading.Lock()
        return _task_locks[task_id]


def register_agent(task_id: str, agent_name: str) -> None:
    with _lock:
        _running_agents.setdefault(task_id, set()).add(agent_name)


def unregister_agent(task_id: str, agent_name: str) -> None:
    with _lock:
        agents = _running_agents.get(task_id)
        if agents:
            agents.discard(agent_name)
            if not agents:
                del _running_agents[task_id]


def cancel_task_process(task_id: str, timeout: int = 30) -> None:
    with _lock:
        agents_to_stop = list(_running_agents.get(task_id, ()))

    if not agents_to_stop:
        return

    logger.info(
        f"[PROCESS] Stopping {len(agents_to_stop)} mngr agents for task {task_id[:8]}"
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
        if task_id in _running_agents:
            del _running_agents[task_id]


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
                if step.status == StepStatus.RUNNING:
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
    """Stop all running mngr agents and mark tasks as PAUSED."""
    task_ids: List[str] = []
    with _lock:
        task_ids = list(_running_agents.keys())

        # Also mark all tasks as PAUSED so they don't look like they failed
        state = _load_state()
        modified = False
        for task in state.tasks:
            if task.status == TaskStatus.RUNNING or task.status == TaskStatus.PENDING:
                task.status = TaskStatus.PAUSED
                modified = True
            for step in task.steps:
                if step.status == StepStatus.RUNNING:
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
