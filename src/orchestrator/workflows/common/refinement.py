from typing import Callable, Optional
from ...models import Task, StepCategory
from ..base import run_step_if_needed
from orchestrator.prompts import (
    get_review_theory_prompt,
    get_refine_theory_prompt,
    get_summarize_research_prompt,
)

def run_refinement_loop(
    task: Task,
    run_step_fn: Callable,
    theory_id: str,
    lit_review_id: Optional[str],
    apply_expansions: Optional[str],
    max_refinements: int,
    stage_prefix: str = "",
    generate_intermediate_research_summaries: bool = False,
) -> str:
    i = 1
    while i <= max_refinements:
        if generate_intermediate_research_summaries:
            run_step_if_needed(
                task,
                run_step_fn,
                f"{stage_prefix}summarize-research-{i}",
                get_summarize_research_prompt(),
                StepCategory.MISC,
            )

        # Review
        review_data = run_step_if_needed(
            task,
            run_step_fn,
            f"{stage_prefix}review-theory-{i}",
            get_review_theory_prompt(theory_id),
            StepCategory.REVIEW,
            cost=3,
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
        refine_data = run_step_if_needed(
            task,
            run_step_fn,
            f"{stage_prefix}refine-theory-{i}",
            get_refine_theory_prompt(theory_id, apply_expansions, lit_review_id),
            StepCategory.THEORY_WRITING,
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


def get_active_max_iterations(task: Task, default_refinements: int) -> int:
    max_iters = default_refinements if default_refinements > 0 else 0
    for s in task.steps:
        if s.stage.startswith("review-theory-") or s.stage.startswith("refine-theory-"):
            try:
                it = int(s.stage.split("-")[-1])
                if it > max_iters:
                    max_iters = it
            except ValueError:
                pass
    return max_iters
