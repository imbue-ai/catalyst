from abc import ABC, abstractmethod
from typing import Any, Callable, List, Dict, Optional
import os
import subprocess
from ..models import Task, StepStatus

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
        if not os.path.exists(task.db_path):
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Initializing DB folder...")
            env = os.environ.copy()
            env["AI_SCIENTIST_DB_PATH"] = task.db_path
            subprocess.run(
                ["uv", "run", "python", "context_manager.py", "init"],
                env=env,
                check=True,
            )

    def get_step_output(self, task: Task, stage_prefix: str) -> Optional[Dict[str, Any]]:
        for s in task.steps:
            if s.stage.startswith(stage_prefix) and s.status == StepStatus.COMPLETED:
                return s.outputs
        return None

    def run_step_if_needed(self, task: Task, run_step_fn: Callable, stage: str, prompt: str) -> Optional[Dict[str, Any]]:
        out = self.get_step_output(task, stage)
        if not out:
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Running {stage}...")
            out = run_step_fn(task, stage, prompt)
        return out
