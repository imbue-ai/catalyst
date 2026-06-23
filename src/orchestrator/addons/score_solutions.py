import json
import logging
from typing import Callable
from ..models import Addon, Task, StepCategory, StepStatus
from .base import AddonHandler
from ..state import get_task_lock
from ..utils import run_context_manager
from orchestrator.prompts import get_score_theory_solutions_prompt

logger = logging.getLogger(__name__)


class ScoreSolutionsAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "score-solutions"

    @property
    def category(self) -> StepCategory:
        return StepCategory.REVIEW

    def run(self, task: Task, run_step: Callable, addon: Addon, index: int) -> None:
        stage = f"addon-{addon.type}-{index}"

        # Check if already completed or canceled
        completed_or_canceled = False
        with get_task_lock(task.id):
            for s in task.steps:
                if s.stage == stage and s.status in (
                    StepStatus.COMPLETED,
                    StepStatus.CANCELED,
                ):
                    completed_or_canceled = True
                    break

        if not completed_or_canceled:
            logger.debug(f"[ORCHESTRATOR] [{task.id[:8]}] Running addon {stage}...")

            try:
                out = run_context_manager(
                    task,
                    [
                        "sample_theories",
                        "--num_theories",
                        "99999",
                        "--purpose",
                        "proposals",
                        "--json",
                    ],
                )
                samples = json.loads(out)
            except Exception as e:
                logger.error(
                    f"Failed to fetch theory latest solutions for score-solutions addon: {e}"
                )
                samples = []

            theory_to_sol = {}
            for s in samples:
                theory_id = s.get("id")
                latest_sol = s.get("latest_solution")
                if theory_id and latest_sol:
                    theory_to_sol[theory_id] = latest_sol

            theory_ids = addon.theory_ids or []
            solution_theory_pairs = []
            for tid in theory_ids:
                sol_id = theory_to_sol.get(tid) or "placeholder"
                solution_theory_pairs.append((sol_id, tid))

            prompt = get_score_theory_solutions_prompt(solution_theory_pairs)
            run_step(task, stage, prompt, cost=self.cost, category=self.category)

    def get_prompt(self, addon: Addon) -> str:
        raise NotImplementedError("ScoreSolutionsAddon overrides run() directly")
