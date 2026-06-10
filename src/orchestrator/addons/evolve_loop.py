from typing import Dict, Any, Callable
from ..models import Addon, Task
from .base import AddonHandler
from ..workflows.common import (
    run_evolve_loop, 
    DEFAULT_EVOLVE_ITERATIONS, 
    DEFAULT_NUM_PARENTS, 
    DEFAULT_MAX_STREAMLINE_PROB, 
    DEFAULT_WRITE_DIFFERENT_PROB,
    DEFAULT_NUM_EXTRA_SCORES
)

class EvolveLoopAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "evolve-loop"

    def get_structure(self, addon: Addon, index: int, task: Task) -> Dict[str, Any]:
        evolve_iterations = addon.evolve_iterations if hasattr(addon, 'evolve_iterations') and addon.evolve_iterations is not None else DEFAULT_EVOLVE_ITERATIONS
        generate_summaries = addon.generate_intermediate_research_summaries if addon.generate_intermediate_research_summaries is not None else False
        
        iteration_structures = {}
        for i in range(1, evolve_iterations + 1):
            iter_struct = []
            
            if generate_summaries:
                iter_struct.append({"type": "step", "stage": f"addon-{index}-summarize-research-{i}"})
            
            # Sample Parents step
            iter_struct.append({"type": "step", "stage": f"addon-{index}-sample-parents-{i}"})

            # Mutate parallel block
            mutate_stages = [s.stage for s in task.steps if s.stage.startswith(f"addon-{index}-mutate-streamline-{i}-") or s.stage.startswith(f"addon-{index}-mutate-refine-{i}-") or s.stage.startswith(f"addon-{index}-mutate-write-different-{i}-")]
            iter_struct.append({"type": "parallel", "name": "Mutate", "stages": mutate_stages})
            
            # Review parallel block
            loop_review_stages = [s.stage for s in task.steps if s.stage.startswith(f"addon-{index}-review-theory-{i}-")]
            iter_struct.append({"type": "parallel", "name": "Review", "stages": loop_review_stages})
            
            # Sample Scoring step
            iter_struct.append({"type": "step", "stage": f"addon-{index}-sample-scoring-{i}"})

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
        max_streamline_prob = addon.max_streamline_prob if hasattr(addon, 'max_streamline_prob') and addon.max_streamline_prob is not None else DEFAULT_MAX_STREAMLINE_PROB
        write_different_prob = addon.write_different_prob if hasattr(addon, 'write_different_prob') and addon.write_different_prob is not None else DEFAULT_WRITE_DIFFERENT_PROB
        num_extra_scores = addon.num_extra_scores if hasattr(addon, 'num_extra_scores') and addon.num_extra_scores is not None else DEFAULT_NUM_EXTRA_SCORES
        apply_expansions = addon.apply_expansions if hasattr(addon, 'apply_expansions') and addon.apply_expansions is not None else None
        lit_review_id = addon.lit_review_id if hasattr(addon, 'lit_review_id') and addon.lit_review_id is not None else None
        generate_summaries = addon.generate_intermediate_research_summaries if addon.generate_intermediate_research_summaries is not None else False

        run_evolve_loop(
            task=task,
            run_step_fn=run_step,
            iterations=evolve_iterations,
            num_parents=num_parents,
            max_streamline_prob=max_streamline_prob,
            write_different_prob=write_different_prob,
            num_extra_scores=num_extra_scores,
            apply_expansions=apply_expansions,
            lit_review_id=lit_review_id,
            stage_prefix=f"addon-{index}-",
            generate_intermediate_research_summaries=generate_summaries,
        )


    def get_prompt(self, addon: Addon) -> str:
        pass
