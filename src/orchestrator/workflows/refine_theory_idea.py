from typing import Any, Callable, List, Dict
from ..models import Task, StepCategory
from .base import Workflow, run_step_if_needed
from .common import (
    DEFAULT_EVOLVE_ITERATIONS,
    DEFAULT_NUM_EXTRA_SCORES,
    DEFAULT_NUM_PARENTS,
    DEFAULT_MAX_STREAMLINE_PROB,
    DEFAULT_WRITE_DIFFERENT_PROB,
    run_evolve_loop,
    run_summarize_title,
    build_evolve_loop_structure,
)
from orchestrator.prompts import (
    get_support_idea_prompt,
    get_review_theory_prompt,
    get_score_theories_prompt,
    get_summarize_research_prompt,
)


class RefineTheoryIdeaWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "refine-theory-idea"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        structure = [
            {"type": "step", "stage": "summarize-title"},
            {"type": "step", "stage": "support-idea"},
            {"type": "step", "stage": "review-theory"},
            {"type": "step", "stage": "score-theories"},
        ]

        evolve_iterations = int(task.workflow_inputs.get("evolve_iterations", 0))
        if evolve_iterations > 0:
            generate_summaries = task.workflow_inputs.get("generate_intermediate_research_summaries")
            if generate_summaries is None:
                generate_summaries = task.generate_summary
            structure.extend(build_evolve_loop_structure(task, evolve_iterations, generate_intermediate_research_summaries=generate_summaries))

        if task.generate_summary:
            structure.append({"type": "step", "stage": "summarize-research"})

        return structure


    def run(self, task: Task, run_step: Callable) -> None:
        idea = task.workflow_inputs.get("idea", "")
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
            # Step 2: Review Theory
            run_step_if_needed(
                task,
                run_step,
                "review-theory",
                get_review_theory_prompt(theory_id),
                StepCategory.REVIEW,
                cost=3,
            )

            # Step 3: Score Theories
            run_step_if_needed(
                task,
                run_step,
                "score-theories",
                get_score_theories_prompt([theory_id]),
                StepCategory.REVIEW,
            )

            # Step 4: Evolve Loop
            evolve_iterations = int(
                task.workflow_inputs.get("evolve_iterations", DEFAULT_EVOLVE_ITERATIONS)
            )
            if evolve_iterations > 0:
                num_parents = int(
                    task.workflow_inputs.get("num_parents", DEFAULT_NUM_PARENTS)
                )
                max_streamline_prob = float(
                    task.workflow_inputs.get("max_streamline_prob", DEFAULT_MAX_STREAMLINE_PROB)
                )
                write_different_prob = float(
                    task.workflow_inputs.get(
                        "write_different_prob", DEFAULT_WRITE_DIFFERENT_PROB
                    )
                )
                num_extra_scores = int(
                    task.workflow_inputs.get(
                        "num_extra_scores", DEFAULT_NUM_EXTRA_SCORES
                    )
                )
                apply_expansions = task.workflow_inputs.get("apply_expansions")

                generate_summaries = task.workflow_inputs.get("generate_intermediate_research_summaries")
                if generate_summaries is None:
                    generate_summaries = task.generate_summary

                run_evolve_loop(
                    task,
                    run_step,
                    iterations=evolve_iterations,
                    num_parents=num_parents,
                    max_streamline_prob=max_streamline_prob,
                    write_different_prob=write_different_prob,
                    num_extra_scores=num_extra_scores,
                    apply_expansions=apply_expansions,
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

