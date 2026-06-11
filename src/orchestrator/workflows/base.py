from abc import ABC, abstractmethod
from typing import Any, Callable, List, Dict, Optional
import os
import logging

from context_manager import DEFAULT_DB_DIR
from ..models import Task, StepStatus, Step
from ..state import update_task, get_task_lock
from ..utils import run_context_manager

logger = logging.getLogger(__name__)


def get_step_output(task: Task, stage_prefix: str) -> Optional[Dict[str, Any]]:
    for s in task.steps:
        if s.stage == stage_prefix and s.status == StepStatus.COMPLETED:
            return s.outputs
    return None


def run_local_step_if_needed(
    task: Task, stage: str, fn: Callable[[], Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    out = get_step_output(task, stage)
    if out is not None:
        return out

    for s in task.steps:
        if s.stage == stage and s.status == StepStatus.CANCELED:
            logger.debug(
                f"[ORCHESTRATOR] [{task.id[:8]}] Skipping canceled local step {stage}..."
            )
            return {"_canceled": True}

    logger.debug(f"[ORCHESTRATOR] [{task.id[:8]}] Running local step {stage}...")

    lock = get_task_lock(task.id)

    with lock:
        step = next((s for s in task.steps if s.stage == stage), None)
        if not step:
            step = Step(stage=stage, status=StepStatus.RUNNING, inputs={})
            task.steps.append(step)
        else:
            step.status = StepStatus.RUNNING
            step.error = None
            step.outputs = None
        update_task(task)

    try:
        out = fn()
        with lock:
            step.status = StepStatus.COMPLETED
            step.outputs = out
            update_task(task)
        return out
    except Exception as e:
        with lock:
            step.status = StepStatus.FAILED
            step.error = str(e)
            update_task(task)
        raise e


def run_step_if_needed(
    task: Task, run_step_fn: Callable, stage: str, prompt: str, cost: int = 1
) -> Optional[Dict[str, Any]]:
    out = get_step_output(task, stage)
    if not out:
        # Check if already canceled to avoid logging "Running"
        for s in task.steps:
            if s.stage == stage and s.status == StepStatus.CANCELED:
                logger.debug(
                    f"[ORCHESTRATOR] [{task.id[:8]}] Skipping canceled step {stage}..."
                )
                return {"_canceled": True}

        logger.debug(f"[ORCHESTRATOR] [{task.id[:8]}] Running {stage} (cost {cost})...")
        out = run_step_fn(task, stage, prompt, cost=cost)
    return out


class Workflow(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        """Returns the structural representation of the workflow for the UI."""
        pass

    @abstractmethod
    def run(self, task: Task, run_step_fn: Callable) -> None:
        """Executes the workflow."""
        pass


class ParallelStepRunner:
    """A context manager to handle parallel execution of workflow steps.

    Usage:
        with ParallelStepRunner() as runner:
            runner.add(some_function, arg1, arg2)
            runner.add(another_function, kwarg1=val)
    """

    def __init__(self) -> None:
        import threading

        self.threads: List[threading.Thread] = []
        self.errors: List[Exception] = []
        self._lock = threading.Lock()

    def __enter__(self) -> "ParallelStepRunner":
        return self

    def add(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        import threading

        def target() -> None:
            try:
                fn(*args, **kwargs)
            except Exception as e:
                with self._lock:
                    self.errors.append(e)

        t = threading.Thread(target=target)
        t.daemon = True
        self.threads.append(t)
        t.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Optional[bool]:
        for t in self.threads:
            t.join()
        if exc_type is None and self.errors:
            raise self.errors[0]
        return False
