import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from .models import Task, TasksState, TaskStatus, StepStatus
from .utils import get_catalyst_path

logger = logging.getLogger(__name__)


def _get_state_file() -> str:
    path = os.path.join(get_catalyst_path(), "tasks_state.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


_lock = threading.Lock()
_task_locks: Dict[str, threading.Lock] = {}


# A piece of in-flight work for a task that external callers
# (cancel/pause/shutdown) need to be able to stop without knowing what
# kind of work it is. Each runner constructs its own Cancellable when
# it spawns work and unregisters on exit; state.py just holds the
# registry. The `cancel(timeout)` callback must be safe to call from
# any thread, idempotent, and must fall back to force-kill if a clean
# stop doesn't complete within `timeout` seconds. `description` is for
# logging only.
@dataclass(frozen=True)
class Cancellable:
    description: str
    cancel: Callable[[float], None]


_running: Dict[str, List[Cancellable]] = {}

_state_cache: Optional[TasksState] = None


def get_task_lock(task_id: str) -> threading.Lock:
    with _lock:
        if task_id not in _task_locks:
            _task_locks[task_id] = threading.Lock()
        return _task_locks[task_id]


def register_cancellable(task_id: str, cancellable: Cancellable) -> None:
    with _lock:
        _running.setdefault(task_id, []).append(cancellable)


def unregister_cancellable(task_id: str, cancellable: Cancellable) -> None:
    with _lock:
        entries = _running.get(task_id)
        if not entries:
            return
        try:
            entries.remove(cancellable)
        except ValueError:
            pass
        if not entries:
            del _running[task_id]


def cancel_task_process(task_id: str, timeout: float = 30) -> None:
    """Cancel everything `task_id` registered. Each Cancellable's
    `cancel(timeout)` runs concurrently so multiple in-flight items
    share the deadline instead of serializing on it."""
    with _lock:
        cancellables = list(_running.get(task_id, ()))

    if not cancellables:
        return

    logger.info(
        f"[PROCESS] Cancelling {len(cancellables)} item(s) for task {task_id[:8]}"
    )
    with ThreadPoolExecutor(max_workers=len(cancellables)) as executor:
        futures = {executor.submit(c.cancel, timeout): c for c in cancellables}
        for fut in as_completed(futures):
            c = futures[fut]
            try:
                fut.result()
            except Exception as e:
                logger.error(f"[PROCESS] cancel({c.description}) failed: {e}")

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
            
            # Resolve relative paths in loaded data using CATALYST_PATH
            catalyst_path = get_catalyst_path()
            for task in data.get("tasks", []):
                env_folder = task.get("env_folder")
                if env_folder and not os.path.isabs(env_folder):
                    task["env_folder"] = os.path.abspath(
                        os.path.join(catalyst_path, env_folder)
                    )

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
    catalyst_path = get_catalyst_path()
    for task in data.get("tasks", []):
        for step in task.get("steps", []):
            if "last_status" in step:
                step["last_status"] = None
        
        env_folder = task.get("env_folder")
        if env_folder:
            abs_env = os.path.abspath(env_folder)
            abs_cat = os.path.abspath(catalyst_path)
            try:
                # We check if env_folder is inside or equal to get_catalyst_path()
                if os.path.commonpath([abs_env, abs_cat]) == abs_cat:
                    task["env_folder"] = os.path.relpath(abs_env, abs_cat)
            except ValueError:
                # E.g. different drives on Windows, fallback to absolute path
                pass

    json_str = json.dumps(data, indent=2)

    # Skip disk write if nothing actually changed
    if _last_written_json == json_str:
        return

    state_file_name = _get_state_file()
    bak_state_file_name = f"{state_file_name}.bak"
    new_state_file_name = f"{state_file_name}.new"

    with open(new_state_file_name, "w") as f:
        f.write(json_str)

    if os.path.exists(state_file_name):
        try:
            os.replace(state_file_name, bak_state_file_name)
        except Exception as e:
            logger.warning(f"Could not create backup of state file: {e}")

    os.replace(new_state_file_name, state_file_name)

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
        logger.info(f"[SHUTDOWN] Stopping agents for {len(task_ids)} tasks...")
        for tid in task_ids:
            cancel_task_process(tid)
