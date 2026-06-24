from typing import Dict, Any, Callable
from ..models import Addon, Task, StepCategory
from .base import AddonHandler
from ..workflows.common import (
    build_solve_goal_loop_structure,
    run_solve_goal_loop,
)


class SolveGoalLoopAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "solve-goal-loop"

    @property
    def category(self) -> StepCategory:
        return StepCategory.MISC

    def get_structure(self, addon: Addon, index: int, task: Task) -> Dict[str, Any]:
        theory_ids = addon.theory_ids or []
        num_strands = len(theory_ids)
        max_iterations = (
            addon.max_iterations if addon.max_iterations is not None else 20
        )
        integration_interval = (
            addon.integration_interval if addon.integration_interval is not None else 5
        )

        return build_solve_goal_loop_structure(
            task=task,
            num_strands=num_strands,
            max_iterations=max_iterations,
            integration_interval=integration_interval,
            stage_prefix=f"addon-{index}-",
        )

    def run(self, task: Task, run_step: Callable, addon: Addon, index: int) -> None:
        theory_ids = addon.theory_ids or []
        max_iterations = (
            addon.max_iterations if addon.max_iterations is not None else 20
        )
        num_executions_per_iteration = (
            addon.num_executions_per_iteration
            if addon.num_executions_per_iteration is not None
            else 2
        )
        execution_cost = addon.execution_cost if addon.execution_cost is not None else 1
        integration_interval = (
            addon.integration_interval if addon.integration_interval is not None else 5
        )

        run_solve_goal_loop(
            task=task,
            run_step=run_step,
            theory_ids=theory_ids,
            max_iterations=max_iterations,
            num_executions_per_iteration=num_executions_per_iteration,
            execution_cost=execution_cost,
            integration_interval=integration_interval,
            stage_prefix=f"addon-{index}-",
        )

    def get_prompt(self, addon: Addon) -> str:
        pass
