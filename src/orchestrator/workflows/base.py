from abc import ABC, abstractmethod
from typing import Any, Callable, List, Dict, Optional
import os
import subprocess
from ..models import Task, StepStatus

def get_step_output(task: Task, stage_prefix: str) -> Optional[Dict[str, Any]]:
    for s in task.steps:
        if s.stage.startswith(stage_prefix) and s.status == StepStatus.COMPLETED:
            return s.outputs
    return None
def run_step_if_needed(task: Task, run_step_fn: Callable, stage: str, prompt: str) -> Optional[Dict[str, Any]]:
    out = get_step_output(task, stage)
    if not out:
        # Check if already canceled to avoid logging "Running"
        for s in task.steps:
            if s.stage == stage and s.status == StepStatus.CANCELED:
                print(f"[ORCHESTRATOR] [{task.id[:8]}] Skipping canceled step {stage}...")
                return {"_canceled": True}

        print(f"[ORCHESTRATOR] [{task.id[:8]}] Running {stage}...")
        out = run_step_fn(task, stage, prompt)
    return out

def run_refinement_loop(task: Task, run_step_fn: Callable, theory_id: str, lit_review_id: Optional[str], apply_extensions: bool, max_refinements: int, stage_prefix: str = "") -> str:
    i = 1
    while i <= max_refinements:
        # Review
        review_data = run_step_if_needed(
            task, run_step_fn, f"{stage_prefix}review-theory-{i}",
            f"Please run the review-theory skill for the following theory_id: {theory_id}. "
            "When you are done, return a JSON object with the key 'review_ids' (a list of strings)."
        )

        if not review_data:
            raise Exception(f"Theory review for iteration {i} failed.")

        if review_data.get("_canceled"):
            i += 1
            continue

        review_ids = review_data.get("review_ids", [])
        if not review_ids:
            break

        # Refine
        prompt = (
            f"Please run the refine-theory skill for the following theory_id: {theory_id}. "
        )
        if lit_review_id:
            prompt += f"Use literature_review_id: {lit_review_id}. "
        prompt += "When you are done, return a JSON object with the keys 'theory_id' and 'major_changes' (boolean) to indicate if any major changes have been made to the theory."

        if not apply_extensions:
            prompt += "\n\nCRITICAL: Do not apply extensions."

        refine_data = run_step_if_needed(
            task, run_step_fn, f"{stage_prefix}refine-theory-{i}", prompt
        )

        if not refine_data:
            raise Exception(f"Theory refinement for iteration {i} failed.")

        if refine_data.get("_canceled"):
            i += 1
            continue

        theory_id = refine_data.get("theory_id") or theory_id
        if not refine_data.get("major_changes", True):
            break

        i += 1

    return theory_id

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
