from typing import Dict, Any, Callable
from ..models import Addon, Task, StepCategory
from .base import AddonHandler
from ..workflows.common import run_refinement_loop

class RefinementLoopAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "refinement-loop"

    @property
    def category(self) -> StepCategory:
        return StepCategory.MISC

    def get_structure(self, addon: Addon, index: int, task: Task) -> Dict[str, Any]:
        max_iters = addon.max_refinements if addon.max_refinements is not None else 3
        base_stages = [f"addon-{index}-review-theory", f"addon-{index}-refine-theory"]
        generate_summaries = addon.generate_intermediate_research_summaries if addon.generate_intermediate_research_summaries is not None else False
        if generate_summaries:
            base_stages.insert(1, f"addon-{index}-summarize-research")
        return {
            "type": "loop",
            "name": "Refinement Loop",
            "base_stages": base_stages,
            "iterations": max_iters,
        }

    def run(self, task: Task, run_step: Callable, addon: Addon, index: int) -> None:
        max_refinements = addon.max_refinements if addon.max_refinements is not None else 3
        apply_expansions = addon.apply_expansions
        generate_summaries = addon.generate_intermediate_research_summaries if addon.generate_intermediate_research_summaries is not None else False
        
        run_refinement_loop(
            task=task,
            run_step_fn=run_step,
            theory_id=addon.theory_id,
            lit_review_id=addon.lit_review_id,
            apply_expansions=apply_expansions,
            max_refinements=max_refinements,
            stage_prefix=f"addon-{index}-",
            generate_intermediate_research_summaries=generate_summaries,
        )


    def get_prompt(self, addon: Addon) -> str:
        pass