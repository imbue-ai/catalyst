import json
import os
import threading
import subprocess
from typing import List, Optional, Dict
from .models import Task, TasksState

STATE_FILE = "tasks_state.json"
_lock = threading.Lock()
_task_locks: Dict[str, threading.Lock] = {}
_running_processes: Dict[str, subprocess.Popen] = {}

def get_task_lock(task_id: str) -> threading.Lock:
    with _lock:
        if task_id not in _task_locks:
            _task_locks[task_id] = threading.Lock()
        return _task_locks[task_id]

def register_process(task_id: str, process: subprocess.Popen):
    with _lock:
        _running_processes[task_id] = process

def unregister_process(task_id: str):
    with _lock:
        if task_id in _running_processes:
            del _running_processes[task_id]

def cancel_task_process(task_id: str):
    with _lock:
        if task_id in _running_processes:
            proc = _running_processes[task_id]
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            del _running_processes[task_id]

def _load_state() -> TasksState:
    if not os.path.exists(STATE_FILE):
        return TasksState(tasks=[])
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return TasksState.model_validate(data)
    except Exception:
        return TasksState(tasks=[])

def _save_state(state: TasksState):
    with open(STATE_FILE, "w") as f:
        json.dump(state.model_dump(), f, indent=2)

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
    with _lock:
        state = _load_state()
        for i, t in enumerate(state.tasks):
            if t.id == task.id:
                state.tasks[i] = task
                break
        _save_state(state)

def initialize_state():
    with _lock:
        state = _load_state()
        modified = False
        for task in state.tasks:
            if task.status == TaskStatus.RUNNING or task.status == TaskStatus.PENDING:
                task.status = TaskStatus.PAUSED
                modified = True
        if modified:
            _save_state(state)

def delete_task(task_id: str):
    with _lock:
        state = _load_state()
        state.tasks = [t for t in state.tasks if t.id != task_id]
        _save_state(state)
        # Also clean up locks and processes if any
        if task_id in _task_locks:
            del _task_locks[task_id]
        if task_id in _running_processes:
            # We should have cancelled it before calling delete_task, 
            # but let's be safe.
            cancel_task_process(task_id)
