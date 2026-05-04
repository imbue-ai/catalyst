from typing import Dict, Any, Callable
from ..models import Addon, Task
from .base import AddonHandler
from ..workflows.common import run_refinement_loop

class RefinementLoopAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "refinement-loop"

    def get_structure(self, addon: Addon, index: int, task: Task) -> Dict[str, Any]:
        max_iters = addon.max_refinements if addon.max_refinements is not None else 3
        return {
            "type": "loop",
            "name": "Refinement Loop",
            "base_stages": [f"addon-{index}-review-theory", f"addon-{index}-refine-theory"],
            "iterations": max_iters,
        }

    def run(self, task: Task, run_step: Callable, addon: Addon, index: int) -> None:
        max_refinements = addon.max_refinements if addon.max_refinements is not None else 3
        apply_extensions = addon.apply_extensions if addon.apply_extensions is not None else False
        
        run_refinement_loop(
            task=task,
            run_step_fn=run_step,
            theory_id=addon.theory_id,
            lit_review_id=None,
            apply_extensions=apply_extensions,
            max_refinements=max_refinements,
            stage_prefix=f"addon-{index}-"
        )

    def get_prompt(self, addon: Addon) -> str:
        pass