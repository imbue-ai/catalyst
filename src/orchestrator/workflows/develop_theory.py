import logging
from typing import Any, Callable, List, Dict
import os
from ..models import Task


from orchestrator.prompts import (
    get_write_n_theories_prompt,
    get_review_theory_prompt,
    get_score_theories_prompt,
    get_summarize_research_prompt,
)

from .base import Workflow, run_step_if_needed, ParallelStepRunner
from .common import (
    DEFAULT_EVOLVE_ITERATIONS,
    DEFAULT_NUM_EXTRA_SCORES,
    DEFAULT_NUM_PARENTS,
    DEFAULT_MAX_STREAMLINE_PROB,
    DEFAULT_WRITE_DIFFERENT_PROB,
    run_evolve_loop,
    run_summarize_title,
    run_literature_review_and_exploration_parallel,
    build_evolve_loop_structure,
)

logger = logging.getLogger(__name__)


class DevelopTheoryWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "develop-theory"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        structure = [
            {"type": "step", "stage": "summarize-title"},
            {
                "type": "parallel",
                "name": "Gather Context",
                "stages": ["literature-review", "explore"],
            },
            {"type": "step", "stage": "write-n-theories"},
        ]

        review_stages = [
            s.stage
            for s in task.steps
            if s.stage.startswith("review-theory-") and len(s.stage.split("-")) == 3
        ]
        if review_stages:
            structure.append(
                {"type": "parallel", "name": "Review Theories", "stages": review_stages}
            )

        structure.append({"type": "step", "stage": "score-theories"})

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

        # Step 3: Write N Theories
        num_theories = task.workflow_inputs.get("num_root_theories", 3)
        theories_data = run_step_if_needed(
            task,
            run_step,
            "write-n-theories",
            get_write_n_theories_prompt(
                num_theories,
                phenomenon,
                exploration_id,
                lit_review_id,
            ),
        )

        theory_ids = theories_data.get("theory_ids") if theories_data else None
        if not theory_ids and not (theories_data and theories_data.get("_canceled")):
            raise Exception("Theory generation failed to return theory IDs.")

        if theory_ids and isinstance(theory_ids, list):
            # Step 4: Parallel Review Theories
            logger.debug(
                f"[ORCHESTRATOR] [{task.id[:8]}] Running {len(theory_ids)} Review Theories in parallel..."
            )
            review_results = {}

            def run_review(tid):
                review_stage = f"review-theory-{tid}"
                res = run_step_if_needed(
                    task,
                    run_step,
                    review_stage,
                    get_review_theory_prompt(tid),
                    cost=3,
                )
                review_results[tid] = res

            with ParallelStepRunner() as runner:
                for tid in theory_ids:
                    runner.add(run_review, tid)

            # Step 5: Score Theories
            run_step_if_needed(
                task,
                run_step,
                "score-theories",
                get_score_theories_prompt(theory_ids),
            )

            # Step 6: Evolve Loop
            evolve_iterations = int(
                task.workflow_inputs.get("evolve_iterations", DEFAULT_EVOLVE_ITERATIONS)
            )
            if evolve_iterations > 0:
                num_parents = int(
                    task.workflow_inputs.get("num_parents", DEFAULT_NUM_PARENTS)
                )
                max_streamline_prob = float(
                    task.workflow_inputs.get(
                        "max_streamline_prob", DEFAULT_MAX_STREAMLINE_PROB
                    )
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
                    lit_review_id=lit_review_id,
                    generate_intermediate_research_summaries=generate_summaries,
                )

            # Final step: stand-alone summarize-research step if enabled
            if task.generate_summary:
                run_step_if_needed(
                    task,
                    run_step,
                    "summarize-research",
                    get_summarize_research_prompt(),
                )

