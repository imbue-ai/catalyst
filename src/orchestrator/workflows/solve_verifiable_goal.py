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
)

logger = logging.getLogger(__name__)


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
        num_strands = int(task.workflow_inputs.get("num_strands", 3))

        def _initialize_theories() -> Dict[str, Any]:
            abs_env_folder = os.path.abspath(task.env_folder)
            tmp_dir = os.path.join(abs_env_folder, "tmp")
            os.makedirs(tmp_dir, exist_ok=True)

            theory_ids = []
            for idx in range(num_strands):
                # Create unique output folder under tmp
                output_dir = tempfile.mkdtemp(
                    prefix=f"initialize-theories-output-strand-{idx + 1}-",
                    dir=tmp_dir,
                )

                # Create theory.md
                theory_file = os.path.join(output_dir, "theory.md")
                with open(theory_file, "w", encoding="utf-8") as f:
                    f.write(
                        "# Starter Theory\n**Research goal:** " + goal.strip() + "\n\n"
                    )

                # Store results using run_context_manager in a subprocess
                out = run_context_manager(
                    task,
                    [
                        "store_results",
                        "--from_agent_type",
                        "initialize-theories",
                        "--from_folder",
                        output_dir,
                    ],
                )

                # Extract theory ID from output
                match = re.search(r"Result stored with ID: (\S+)", out)
                if not match:
                    raise Exception(f"Failed to parse stored results ID. Output: {out}")
                theory_ids.append(match.group(1))

            return {"theory_ids": theory_ids}

        init_data = run_local_step_if_needed(
            task,
            "initialize-theories",
            _initialize_theories,
        )

        theory_ids = []
        if init_data:
            theory_ids = init_data.get("theory_ids") or []

        if not theory_ids:
            if init_data and init_data.get("_canceled"):
                return
            raise Exception("Initialization failed to return theory IDs.")

        max_iterations = int(task.workflow_inputs.get("max_iterations", 20))

        run_evolve_solution_loop(
            task=task,
            run_step=run_step,
            theory_ids=theory_ids,
            max_iterations=max_iterations,
            stage_prefix="",
        )
