from typing import Dict, Any, Callable
from ..models import Addon, Task
from .base import AddonHandler
from ..workflows.base import (
    run_evolve_loop, 
    DEFAULT_EVOLVE_ITERATIONS, 
    DEFAULT_NUM_PARENTS, 
    DEFAULT_STREAMLINE_PROB, 
    DEFAULT_NUM_EXTRA_SCORES
)

class EvolveLoopAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "evolve-loop"

    def get_structure(self, addon: Addon, index: int, task: Task) -> Dict[str, Any]:
        evolve_iterations = addon.evolve_iterations if hasattr(addon, 'evolve_iterations') and addon.evolve_iterations is not None else DEFAULT_EVOLVE_ITERATIONS
        
        iteration_structures = {}
        for i in range(1, evolve_iterations + 1):
            iter_struct = []
            
            # Mutate parallel block
            mutate_stages = [s.stage for s in task.steps if s.stage.startswith(f"addon-{index}-mutate-streamline-{i}-") or s.stage.startswith(f"addon-{index}-mutate-refine-{i}-")]
            iter_struct.append({"type": "parallel", "name": "Mutate", "stages": mutate_stages})
            
            # Review parallel block
            loop_review_stages = [s.stage for s in task.steps if s.stage.startswith(f"addon-{index}-review-theory-{i}-")]
            iter_struct.append({"type": "parallel", "name": "Review", "stages": loop_review_stages})
            
            # Score step
            iter_struct.append({"type": "step", "stage": f"addon-{index}-score-theories-{i}"})
            
            iteration_structures[str(i)] = iter_struct

        return {
            "type": "loop",
            "name": "Evolve Theories",
            "iterations": evolve_iterations,
            "iteration_structures": iteration_structures
        }

    def run(self, task: Task, run_step: Callable, addon: Addon, index: int) -> None:
        evolve_iterations = addon.evolve_iterations if hasattr(addon, 'evolve_iterations') and addon.evolve_iterations is not None else DEFAULT_EVOLVE_ITERATIONS
        num_parents = addon.num_parents if hasattr(addon, 'num_parents') and addon.num_parents is not None else DEFAULT_NUM_PARENTS
        streamline_prob = addon.streamline_prob if hasattr(addon, 'streamline_prob') and addon.streamline_prob is not None else DEFAULT_STREAMLINE_PROB
        num_extra_scores = addon.num_extra_scores if hasattr(addon, 'num_extra_scores') and addon.num_extra_scores is not None else DEFAULT_NUM_EXTRA_SCORES
        apply_extensions = addon.apply_extensions if hasattr(addon, 'apply_extensions') and addon.apply_extensions is not None else False
        
        run_evolve_loop(
            task=task,
            run_step_fn=run_step,
            iterations=evolve_iterations,
            num_parents=num_parents,
            streamline_prob=streamline_prob,
            num_extra_scores=num_extra_scores,
            apply_extensions=apply_extensions,
            stage_prefix=f"addon-{index}-"
        )

    def get_prompt(self, addon: Addon) -> str:
        pass