from typing import Any, Callable, Dict, List

from ..models import Task
from .base import Workflow, run_step_if_needed


class SmokeWorkflow(Workflow):
    """Single-step workflow used to validate the orchestrator + agent runner
    plumbing without paying for a real research task.

    The prompt invokes the `/smoke` skill, which is hard-coded to print
    `{"skill_ran": true}` as its final message and stop. This keeps Stage
    C of the verification plan (orchestrator-driven smoke test) bounded to
    a few seconds.
    """

    @property
    def name(self) -> str:
        return "_smoke"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        return [{"type": "step", "stage": "smoke"}]

    def run(self, task: Task, run_step: Callable) -> None:
        # init_db is required by the orchestrator's per-step
        # context_manager commit; without it the smoke step succeeds but
        # the post-step commit raises.
        self.init_db(task)

        prompt = (
            "Run the `/smoke` skill. Follow its instructions exactly: "
            'output `{"skill_ran": true}` as your final message and stop.'
        )
        run_step_if_needed(task, run_step, "smoke", prompt)
