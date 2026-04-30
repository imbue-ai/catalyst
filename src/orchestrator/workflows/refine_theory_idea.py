from typing import Any, Callable, List, Dict
from ..models import Task
from .base import Workflow, run_step_if_needed
from .common import (
    DEFAULT_EVOLVE_ITERATIONS,
    DEFAULT_NUM_EXTRA_SCORES,
    DEFAULT_NUM_PARENTS,
    DEFAULT_STREAMLINE_PROB,
    run_evolve_loop,
    run_summarize_title,
)
from orchestrator.prompts import (
    get_support_idea_prompt,
    get_review_theory_prompt,
    get_score_theories_prompt,
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
            iteration_structures = {}
            for i in range(1, evolve_iterations + 1):
                iter_struct = []

                # Mutate parallel block
                mutate_stages = [
                    s.stage
                    for s in task.steps
                    if s.stage.startswith(f"mutate-streamline-{i}-")
                    or s.stage.startswith(f"mutate-refine-{i}-")
                ]
                iter_struct.append(
                    {"type": "parallel", "name": "Mutate", "stages": mutate_stages}
                )

                # Review parallel block
                loop_review_stages = [
                    s.stage
                    for s in task.steps
                    if s.stage.startswith(f"review-theory-{i}-")
                ]
                iter_struct.append(
                    {"type": "parallel", "name": "Review", "stages": loop_review_stages}
                )

                # Score step
                iter_struct.append({"type": "step", "stage": f"score-theories-{i}"})

                iteration_structures[str(i)] = iter_struct

            structure.append(
                {
                    "type": "loop",
                    "name": "Evolve Theories",
                    "iterations": evolve_iterations,
                    "iteration_structures": iteration_structures,
                }
            )

        return structure

    def run(self, task: Task, run_step: Callable) -> None:
        self.init_db(task)

        idea = task.workflow_inputs.get("idea", "")

        # Step 0: Summarize Title
        run_summarize_title(task, run_step, f"idea: {idea}")

        # Step 1: Support Idea
        support_data = run_step_if_needed(
            task,
            run_step,
            "support-idea",
            get_support_idea_prompt(idea),
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
            )

            # Step 3: Score Theories
            run_step_if_needed(
                task,
                run_step,
                "score-theories",
                get_score_theories_prompt([theory_id]),
            )

            # Step 4: Evolve Loop
            evolve_iterations = int(
                task.workflow_inputs.get("evolve_iterations", DEFAULT_EVOLVE_ITERATIONS)
            )
            if evolve_iterations > 0:
                num_parents = int(
                    task.workflow_inputs.get("num_parents", DEFAULT_NUM_PARENTS)
                )
                streamline_prob = float(
                    task.workflow_inputs.get("streamline_prob", DEFAULT_STREAMLINE_PROB)
                )
                num_extra_scores = int(
                    task.workflow_inputs.get(
                        "num_extra_scores", DEFAULT_NUM_EXTRA_SCORES
                    )
                )
                apply_extensions = task.workflow_inputs.get("apply_extensions", False)

                run_evolve_loop(
                    task,
                    run_step,
                    iterations=evolve_iterations,
                    num_parents=num_parents,
                    streamline_prob=streamline_prob,
                    num_extra_scores=num_extra_scores,
                    apply_extensions=apply_extensions,
                )
