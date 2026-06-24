import logging
import os
import re
import tempfile
from typing import Any, Callable, List, Dict

from ..models import Task, StepCategory
from ..utils import run_context_manager
from .base import (
    Workflow,
    run_local_step_if_needed,
    run_step_if_needed,
)
from .common import (
    run_summarize_title,
    build_evolve_solution_loop_structure,
    run_evolve_solution_loop,
    run_initialize_theories,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_RESCORE_INTERVAL,
    DEFAULT_NUM_EXTRA_INTERPRETATIONS,
    DEFAULT_NUM_PARENTS,
    DEFAULT_NUM_EXTRA_SCORES,
    DEFAULT_NUM_EXECUTIONS_PER_ITERATION,
    DEFAULT_EXECUTION_COST,
    DEFAULT_BRANCH_PROB,
    DEFAULT_NUM_PROPOSALS,
)
from orchestrator.prompts import get_summarize_goal_progress_prompt


logger = logging.getLogger(__name__)


def run_initialize_solutions(task: Task, theory_ids: List[str]) -> List[tuple[str, str]]:
    """Initializes starter solutions for each starter theory.

    Runs as a local step and returns a list of (solution_id, theory_id) tuples.
    """
    def _initialize_solutions() -> Dict[str, Any]:
        abs_env_folder = os.path.abspath(task.env_folder)
        tmp_dir = os.path.join(abs_env_folder, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)

        solution_theory_pairs = []
        for idx, theory_id in enumerate(theory_ids):
            # Create unique output folder under tmp
            output_dir = tempfile.mkdtemp(
                prefix=f"initialize-solutions-output-strand-{idx + 1}-",
                dir=tmp_dir,
            )

            # Create solution.md
            solution_file = os.path.join(output_dir, "solution.md")
            with open(solution_file, "w", encoding="utf-8") as f:
                f.write(
                    "# Placeholder Solution\n"
                    "This is a placeholder solution. No research has been conducted yet, and the goal has not yet been solved.\n"
                )

            # Store results using run_context_manager in a subprocess
            out = run_context_manager(
                task,
                [
                    "store_results",
                    "--from_agent_type",
                    "generate-solution",
                    "--from_folder",
                    output_dir,
                    "--parent_theory",
                    theory_id,
                ],
            )

            # Extract solution ID from output
            match = re.search(r"Result stored with ID: (\S+)", out)
            if not match:
                raise Exception(f"Failed to parse stored solution ID. Output: {out}")
            solution_theory_pairs.append((match.group(1), theory_id))

        return {"solution_theory_pairs": solution_theory_pairs}

    init_data = run_local_step_if_needed(
        task,
        "initialize-solutions",
        _initialize_solutions,
    )

    pairs = []
    if init_data:
        pairs = init_data.get("solution_theory_pairs") or []

    if not pairs:
        if init_data and init_data.get("_canceled"):
            return []
        raise Exception("Initialization of solutions failed to return any pairs.")

    return [(sol, parent) for sol, parent in pairs]


class SolveVerifiableGoalWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "solve-verifiable-goal"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        max_iterations = int(task.workflow_inputs.get("max_iterations", DEFAULT_MAX_ITERATIONS))
        rescore_interval = int(task.workflow_inputs.get("rescore_interval", DEFAULT_RESCORE_INTERVAL))
        generate_summaries_val = task.workflow_inputs.get("generate_intermediate_research_summaries")
        generate_summaries = True if generate_summaries_val is None else bool(generate_summaries_val)

        structure = [
            {"type": "step", "stage": "summarize-title"},
        ]

        if generate_summaries:
            structure.append({"type": "step", "stage": "summarize-goal-progress"})

        structure.extend([
            {"type": "step", "stage": "initialize-theories"},
            {"type": "step", "stage": "initialize-solutions"},
        ])

        if max_iterations > 0:
            loop_struct = build_evolve_solution_loop_structure(
                task=task,
                max_iterations=max_iterations,
                rescore_interval=rescore_interval,
                generate_intermediate_research_summaries=generate_summaries,
                stage_prefix="",
            )
            structure.append(loop_struct)

        return structure

    def run(self, task: Task, run_step: Callable) -> None:
        goal = task.workflow_inputs.get("goal")
        assert goal, "Goal is required."
        verification_instructions = task.workflow_inputs.get(
            "verification_instructions"
        )
        assert verification_instructions, "Verification instructions are required."

        with open(os.path.join(task.env_folder, "goal.txt"), "w") as f:
            f.write(goal.strip() + "\n")

        with open(
            os.path.join(task.env_folder, "verification_instructions.txt"), "w"
        ) as f:
            f.write(verification_instructions.strip() + "\n")

        # Step 0: Summarize Title
        run_summarize_title(task, run_step, f"goal: {goal}")

        generate_summaries_val = task.workflow_inputs.get("generate_intermediate_research_summaries")
        generate_summaries = True if generate_summaries_val is None else bool(generate_summaries_val)
        if generate_summaries:
            run_step_if_needed(
                task,
                run_step,
                "summarize-goal-progress",
                get_summarize_goal_progress_prompt(),
                StepCategory.MISC,
            )

        # Step 1: Initialize Theories
        theory_ids = run_initialize_theories(task)
        if theory_ids is None:
            return

        # Step 1b: Initialize Solutions
        solution_theory_pairs = run_initialize_solutions(task, theory_ids)
        if not solution_theory_pairs:
            return

        max_iterations = int(task.workflow_inputs.get("max_iterations", DEFAULT_MAX_ITERATIONS))
        num_proposals = int(task.workflow_inputs.get("num_proposals", DEFAULT_NUM_PROPOSALS))
        num_extra_interpretations = int(task.workflow_inputs.get("num_extra_interpretations", DEFAULT_NUM_EXTRA_INTERPRETATIONS))
        num_parents = int(task.workflow_inputs.get("num_parents", DEFAULT_NUM_PARENTS))
        num_extra_scores = int(task.workflow_inputs.get("num_extra_scores", DEFAULT_NUM_EXTRA_SCORES))
        rescore_interval = int(task.workflow_inputs.get("rescore_interval", DEFAULT_RESCORE_INTERVAL))
        num_executions_per_iteration = int(task.workflow_inputs.get("num_executions_per_iteration", DEFAULT_NUM_EXECUTIONS_PER_ITERATION))
        execution_cost = int(task.workflow_inputs.get("execution_cost", DEFAULT_EXECUTION_COST))
        branch_prob = float(task.workflow_inputs.get("branch_prob", DEFAULT_BRANCH_PROB))

        run_evolve_solution_loop(
            task=task,
            run_step=run_step,
            max_iterations=max_iterations,
            num_proposals=num_proposals,
            num_extra_interpretations=num_extra_interpretations,
            num_parents=num_parents,
            num_extra_scores=num_extra_scores,
            rescore_interval=rescore_interval,
            num_executions_per_iteration=num_executions_per_iteration,
            execution_cost=execution_cost,
            branch_prob=branch_prob,
            generate_intermediate_research_summaries=generate_summaries,
            stage_prefix="",
        )

