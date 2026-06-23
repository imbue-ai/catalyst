import logging
import os
import re
import tempfile
from typing import Any, Callable, List, Dict

from ..models import Task
from ..utils import run_context_manager
from .base import (
    Workflow,
    run_local_step_if_needed,
)
from .common import (
    run_summarize_title,
    build_evolve_solution_loop_structure,
    run_evolve_solution_loop,
    run_initialize_theories,
)


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
        num_strands = int(task.workflow_inputs.get("num_strands", 3))
        max_iterations = int(task.workflow_inputs.get("max_iterations", 20))

        structure = [
            {"type": "step", "stage": "summarize-title"},
            {"type": "step", "stage": "initialize-theories"},
            {"type": "step", "stage": "initialize-solutions"},
        ]

        if max_iterations > 0:
            loop_struct = build_evolve_solution_loop_structure(
                task,
                num_strands=num_strands,
                max_iterations=max_iterations,
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

        # Step 1: Initialize Theories
        theory_ids = run_initialize_theories(task)
        if theory_ids is None:
            return

        # Step 1b: Initialize Solutions
        solution_theory_pairs = run_initialize_solutions(task, theory_ids)
        if not solution_theory_pairs:
            return

        max_iterations = int(task.workflow_inputs.get("max_iterations", 20))

        run_evolve_solution_loop(
            task=task,
            run_step=run_step,
            theory_ids=theory_ids,
            max_iterations=max_iterations,
            stage_prefix="",
        )

