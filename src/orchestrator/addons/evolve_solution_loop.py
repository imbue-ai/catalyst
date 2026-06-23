from typing import Dict, Any, Callable
from ..models import Addon, Task, StepCategory
from .base import AddonHandler
from ..workflows.common import (
    build_evolve_solution_loop_structure,
    run_evolve_solution_loop,
)


class EvolveSolutionLoopAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "evolve-solution-loop"

    @property
    def category(self) -> StepCategory:
        return StepCategory.MISC

    def get_structure(self, addon: Addon, index: int, task: Task) -> Dict[str, Any]:
        theory_ids = addon.theory_ids or []
        num_strands = len(theory_ids)
        max_iterations = (
            addon.max_iterations if addon.max_iterations is not None else 20
        )

        return build_evolve_solution_loop_structure(
            task=task,
            num_strands=num_strands,
            max_iterations=max_iterations,
            stage_prefix=f"addon-{index}-",
        )

    def run(self, task: Task, run_step: Callable, addon: Addon, index: int) -> None:
        theory_ids = addon.theory_ids or []
        max_iterations = (
            addon.max_iterations if addon.max_iterations is not None else 20
        )

        run_evolve_solution_loop(
            task=task,
            run_step=run_step,
            theory_ids=theory_ids,
            max_iterations=max_iterations,
            stage_prefix=f"addon-{index}-",
        )

    def get_prompt(self, addon: Addon) -> str:
        pass
