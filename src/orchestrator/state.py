import json
import os
import threading
import subprocess
import signal
import time
from typing import List, Optional, Dict
from .models import Task, TasksState, TaskStatus, StepStatus

STATE_FILE = "tasks_state.json"
_lock = threading.Lock()
_task_locks: Dict[str, threading.Lock] = {}
_running_processes: Dict[str, List[subprocess.Popen]] = {}

# In-memory cache to preserve transient fields like last_status
_state_cache: Optional[TasksState] = None

def get_task_lock(task_id: str) -> threading.Lock:
    with _lock:
        if task_id not in _task_locks:
            _task_locks[task_id] = threading.Lock()
        return _task_locks[task_id]

def register_process(task_id: str, process: subprocess.Popen):
    with _lock:
        if task_id not in _running_processes:
            _running_processes[task_id] = []
        _running_processes[task_id].append(process)

def unregister_process(task_id: str, process: subprocess.Popen):
    with _lock:
        if task_id in _running_processes:
            try:
                _running_processes[task_id].remove(process)
            except ValueError:
                pass
            if not _running_processes[task_id]:
                del _running_processes[task_id]

def cancel_task_process(task_id: str, timeout: int = 15):
    processes_to_cancel = []
    with _lock:
        if task_id in _running_processes:
            processes_to_cancel = _running_processes[task_id][:]
    
    if not processes_to_cancel:
        return

    print(f"[PROCESS] Pausing {len(processes_to_cancel)} processes for task {task_id[:8]}")

    for proc in processes_to_cancel:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception as e:
            print(f"[PROCESS] Failed to SIGTERM group for pid {proc.pid}: {e}")
    
    deadline = time.time() + timeout
    for proc in processes_to_cancel:
        remaining = max(0, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            print(f"[PROCESS] PID {proc.pid} didn't exit after {timeout}s, sending SIGKILL to group")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait(timeout=5)
            except Exception as e:
                print(f"[PROCESS] Failed to SIGKILL group for pid {proc.pid}: {e}")
        except Exception:
            pass
            
    with _lock:
        if task_id in _running_processes:
            del _running_processes[task_id]

def _load_state() -> TasksState:
    global _state_cache
    if _state_cache is not None:
        return _state_cache

    if not os.path.exists(STATE_FILE):
        _state_cache = TasksState(tasks=[])
        return _state_cache
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            _state_cache = TasksState.model_validate(data)
            return _state_cache
    except Exception:
        _state_cache = TasksState(tasks=[])
        return _state_cache

def _save_state(state: TasksState):
    global _state_cache
    _state_cache = state
    
    # Strip transient fields like last_status before saving to disk
    data = state.model_dump()
    for task in data.get("tasks", []):
        for step in task.get("steps", []):
            if "last_status" in step:
                step["last_status"] = None
                
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)

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
    """Forcefully terminate all running agent processes across all tasks and mark them as PAUSED."""
    task_ids = []
    with _lock:
        task_ids = list(_running_processes.keys())
        
        # Also mark all tasks as PAUSED so they don't look like they failed
        state = _load_state()
        modified = False
        for task in state.tasks:
            if task.status == TaskStatus.RUNNING or task.status == TaskStatus.PENDING:
                task.status = TaskStatus.PAUSED
                for step in task.steps:
                    if step.status == StepStatus.RUNNING:
                        step.status = StepStatus.PAUSED
                modified = True
        if modified:
            _save_state(state)
    
    if task_ids:
        print(f"[SHUTDOWN] Terminating agent processes for {len(task_ids)} tasks...")
        # Use a shorter timeout during shutdown to avoid hanging the server exit
        for tid in task_ids:
            cancel_task_process(tid, timeout=5)
