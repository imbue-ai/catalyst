import logging
import os
from typing import Any, Callable, List, Dict

from ..models import Task
from .base import (
    Workflow,
)
from .common import (
    run_summarize_title,
    build_solve_goal_loop_structure,
    run_solve_goal_loop,
    run_initialize_theories,
)


logger = logging.getLogger(__name__)


class SolveVerifiableGoalMultiStrandWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "solve-verifiable-goal-multi-strand"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        num_strands = int(task.workflow_inputs.get("num_strands", 3))
        max_iterations = int(task.workflow_inputs.get("max_iterations", 20))
        integration_interval = int(task.workflow_inputs.get("integration_interval", 5))

        structure = [
            {"type": "step", "stage": "summarize-title"},
            {"type": "step", "stage": "initialize-theories"},
        ]

        if max_iterations > 0:
            loop_struct = build_solve_goal_loop_structure(
                task,
                num_strands=num_strands,
                max_iterations=max_iterations,
                integration_interval=integration_interval,
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

        max_iterations = int(task.workflow_inputs.get("max_iterations", 20))
        num_executions_per_iteration = int(
            task.workflow_inputs.get("num_executions_per_iteration", 2)
        )
        execution_cost = int(task.workflow_inputs.get("execution_cost", 1))
        integration_interval = int(task.workflow_inputs.get("integration_interval", 5))

        run_solve_goal_loop(
            task=task,
            run_step=run_step,
            theory_ids=theory_ids,
            max_iterations=max_iterations,
            num_executions_per_iteration=num_executions_per_iteration,
            execution_cost=execution_cost,
            integration_interval=integration_interval,
            stage_prefix="",
        )
