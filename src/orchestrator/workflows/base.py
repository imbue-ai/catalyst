from abc import ABC, abstractmethod
from typing import Any, Callable, List, Dict, Optional
import os
import logging
from ..models import Task, StepStatus

logger = logging.getLogger(__name__)

def get_step_output(task: Task, stage_prefix: str) -> Optional[Dict[str, Any]]:
    for s in task.steps:
        if s.stage == stage_prefix and s.status == StepStatus.COMPLETED:
            return s.outputs
    return None

def run_step_if_needed(
    task: Task, run_step_fn: Callable, stage: str, prompt: str
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

        logger.debug(f"[ORCHESTRATOR] [{task.id[:8]}] Running {stage}...")
        out = run_step_fn(task, stage, prompt)
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

    def init_db(self, task: Task) -> None:
        from .common import run_context_manager
        db_path = os.path.join(task.env_folder, ".ai-scientist-db")
        if not os.path.exists(db_path):
            logger.debug(f"[ORCHESTRATOR] [{task.id[:8]}] Initializing DB folder...")
            run_context_manager(task, ["init"])
