from typing import Any, Callable, List, Dict
from ..models import Task, StepCategory
from .base import Workflow, run_step_if_needed
from .common import run_refinement_loop, run_summarize_title, get_active_max_iterations
from orchestrator.prompts import get_support_idea_prompt, get_summarize_research_prompt

class RefineTheoryIdeaLinearWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "refine-theory-idea-linear"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        max_refinements = int(task.workflow_inputs.get("max_refinements", 3))
        max_iters = get_active_max_iterations(task, max_refinements)

        structure = [
            {"type": "step", "stage": "summarize-title"},
            {"type": "step", "stage": "support-idea"},
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
        idea = task.workflow_inputs.get("idea", "")
        apply_expansions = task.workflow_inputs.get("apply_expansions")
        file_path = task.workflow_inputs.get("file_path")

        content_desc = f"idea: {idea}"
        if file_path:
            content_desc += f" (with uploaded files at {file_path})"

        # Step 0: Summarize Title
        run_summarize_title(task, run_step, content_desc)

        # Step 1: Support Idea
        support_data = run_step_if_needed(
            task,
            run_step,
            "support-idea",
            get_support_idea_prompt(idea, file_path),
            StepCategory.THEORY_WRITING,
        )
        theory_id = support_data.get("theory_id") if support_data else None
        if not theory_id and not (support_data and support_data.get("_canceled")):
            raise Exception("support-idea failed to return a theory ID.")

        if theory_id:
            # Step 2: Iterative Review and Refinement
            max_refinements = int(task.workflow_inputs.get("max_refinements", 3))
            generate_summaries = task.workflow_inputs.get("generate_intermediate_research_summaries")
            if generate_summaries is None:
                generate_summaries = task.generate_summary

            run_refinement_loop(
                task,
                run_step,
                theory_id,
                lit_review_id=None,
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

