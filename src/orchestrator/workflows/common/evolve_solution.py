import logging
from typing import Any, Callable, Dict, List
from ...models import Task
from ..base import run_local_step_if_needed

logger = logging.getLogger(__name__)


def build_evolve_solution_loop_structure(
    task: Task,
    num_strands: int,
    max_iterations: int,
    stage_prefix: str = "",
) -> Dict[str, Any]:
    if max_iterations <= 0:
        return {}

    iteration_structures = {}
    for i in range(1, max_iterations + 1):
        # Create a placeholder step for the loop iteration.
        iter_struct = [
            {"type": "step", "stage": f"{stage_prefix}evolve-solution-step-{i}"}
        ]
        iteration_structures[str(i)] = iter_struct

    return {
        "type": "loop",
        "name": "Evolve Solution Loop",
        "iterations": max_iterations,
        "iteration_structures": iteration_structures,
    }


def run_evolve_solution_loop(
    task: Task,
    run_step: Callable,
    theory_ids: List[str],
    max_iterations: int,
    stage_prefix: str = "",
) -> None:
    for i in range(1, max_iterations + 1):
        def _dummy_step() -> Dict[str, Any]:
            return {"status": "placeholder"}

        run_local_step_if_needed(
            task,
            f"{stage_prefix}evolve-solution-step-{i}",
            _dummy_step,
        )
