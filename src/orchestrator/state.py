import json
import os
import threading
import subprocess
import signal
from typing import List, Optional, Dict
from .models import Task, TasksState, TaskStatus, StepStatus

STATE_FILE = "tasks_state.json"
_lock = threading.Lock()
_task_locks: Dict[str, threading.Lock] = {}
_running_processes: Dict[str, List[subprocess.Popen]] = {}

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

def cancel_task_process(task_id: str):
    # We copy the list while holding the lock, but we perform the actual 
    # process waiting/killing OUTSIDE the lock. This is critical to prevent
    # deadlocks if another thread (like the agent output reader) is trying
    # to acquire the lock to unregister itself.
    processes_to_cancel = []
    with _lock:
        if task_id in _running_processes:
            processes_to_cancel = _running_processes[task_id][:]
    
    if not processes_to_cancel:
        return

    print(f"[PROCESS] Pausing {len(processes_to_cancel)} processes for task {task_id[:8]}")

    # 1. Terminate all process groups
    for proc in processes_to_cancel:
        try:
            # We use killpg because we started them with start_new_session=True
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception as e:
            print(f"[PROCESS] Failed to SIGTERM group for pid {proc.pid}: {e}")
    
    # 2. Wait and Kill groups if needed
    for proc in processes_to_cancel:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"[PROCESS] PID {proc.pid} didn't exit, sending SIGKILL to group")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait()
            except Exception as e:
                print(f"[PROCESS] Failed to SIGKILL group for pid {proc.pid}: {e}")
        except Exception:
            pass
            
    # 3. Final cleanup of the registry
    with _lock:
        if task_id in _running_processes:
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
                for step in task.steps:
                    if step.status == StepStatus.RUNNING:
                        step.status = StepStatus.PAUSED
                modified = True
        if modified:
            _save_state(state)

def delete_task(task_id: str):
    # Performance/Deadlock Fix: Perform cancellation logic OUTSIDE the main lock
    # but still clean up state within locks.
    cancel_task_process(task_id)
    
    with _lock:
        state = _load_state()
        state.tasks = [t for t in state.tasks if t.id != task_id]
        _save_state(state)
        # Clean up task-specific lock
        if task_id in _task_locks:
            del _task_locks[task_id]
