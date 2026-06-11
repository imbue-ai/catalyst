import logging
from typing import Any, Callable, List, Dict
import os
from ..models import Task, StepCategory
from .base import (
    Workflow,
    run_step_if_needed,
)
from .common import (
    run_refinement_loop,
    run_summarize_title,
    run_literature_review_and_exploration_parallel,
    get_active_max_iterations,
)
from orchestrator.prompts import get_write_theory_prompt, get_summarize_research_prompt

logger = logging.getLogger(__name__)


class DevelopTheoryLinearWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "develop-theory-linear"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        max_refinements = int(task.workflow_inputs.get("max_refinements", 3))
        max_iters = get_active_max_iterations(task, max_refinements)

        structure = [
            {"type": "step", "stage": "summarize-title"},
            {
                "type": "parallel",
                "name": "Gather Context",
                "stages": ["literature-review", "explore"],
            },
            {"type": "step", "stage": "write-theory"},
        ]

        if max_iters > 0:
            base_stages = ["review-theory", "refine-theory"]
            generate_summaries = task.workflow_inputs.get("generate_intermediate_research_summaries")
            if generate_summaries is None:
                generate_summaries = task.generate_summary
            if generate_summaries:
                base_stages.insert(1, "summarize-research")

            structure.append(
                {
                    "type": "loop",
                    "name": "Refinement Loop",
                    "base_stages": base_stages,
                    "iterations": max_iters,
                }
            )

        if task.generate_summary:
            structure.append({"type": "step", "stage": "summarize-research"})

        return structure


    def run(self, task: Task, run_step: Callable) -> None:
        phenomenon = task.workflow_inputs.get("phenomenon")
        assert phenomenon
        with open(os.path.join(task.env_folder, "phenomenon.txt"), "w") as f:
            f.write(phenomenon.strip() + "\n")

        # Step 0: Summarize Title
        run_summarize_title(task, run_step, f"phenomenon: {phenomenon}")

        # Step 1 & 2: Literature Review and Exploration in Parallel
        lit_review_id, exploration_id = run_literature_review_and_exploration_parallel(
            task, run_step, phenomenon
        )

        # Step 3: Initial Theory
        theory_data = run_step_if_needed(
            task,
            run_step,
            "write-theory",
            get_write_theory_prompt(
                phenomenon,
                exploration_id,
                lit_review_id,
            ),
            StepCategory.THEORY_WRITING,
        )
        theory_id = theory_data.get("theory_id") if theory_data else None
        if not theory_id and not (theory_data and theory_data.get("_canceled")):
            raise Exception("Theory generation failed to return a theory ID.")

        if theory_id:
            # Step 4: Iterative Review and Refinement
            max_refinements = int(task.workflow_inputs.get("max_refinements", 3))
            apply_expansions = task.workflow_inputs.get("apply_expansions")
            generate_summaries = task.workflow_inputs.get("generate_intermediate_research_summaries")
            if generate_summaries is None:
                generate_summaries = task.generate_summary

            run_refinement_loop(
                task,
                run_step,
                theory_id,
                lit_review_id,
                apply_expansions=apply_expansions,
                max_refinements=max_refinements,
                generate_intermediate_research_summaries=generate_summaries,
            )

        if task.generate_summary:
            run_step_if_needed(
                task,
                run_step,
                "summarize-research",
                get_summarize_research_prompt(),
                StepCategory.MISC,
            )

