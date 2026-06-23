from typing import Dict, Any, Callable
from ..models import Addon, Task, StepCategory
from .base import AddonHandler
from ..workflows.common import (
    build_evolve_solution_loop_structure,
    run_evolve_solution_loop,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_RESCORE_INTERVAL,
    DEFAULT_NUM_INTERPRETATIONS,
    DEFAULT_NUM_PARENTS,
    DEFAULT_NUM_EXTRA_SCORES,
    DEFAULT_NUM_EXECUTIONS_PER_ITERATION,
    DEFAULT_EXECUTION_COST,
    DEFAULT_BRANCH_PROB,
    DEFAULT_NUM_PROPOSALS,
)


class EvolveSolutionLoopAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "evolve-solution-loop"

    @property
    def category(self) -> StepCategory:
        return StepCategory.MISC

    def get_structure(self, addon: Addon, index: int, task: Task) -> Dict[str, Any]:
        max_iterations = (
            addon.max_iterations if addon.max_iterations is not None else DEFAULT_MAX_ITERATIONS
        )
        rescore_interval = (
            addon.rescore_interval if addon.rescore_interval is not None else DEFAULT_RESCORE_INTERVAL
        )
        generate_summaries = (
            addon.generate_intermediate_research_summaries
            if addon.generate_intermediate_research_summaries is not None
            else False
        )

        return build_evolve_solution_loop_structure(
            task=task,
            max_iterations=max_iterations,
            rescore_interval=rescore_interval,
            generate_intermediate_research_summaries=generate_summaries,
            stage_prefix=f"addon-{index}-",
        )

    def run(self, task: Task, run_step: Callable, addon: Addon, index: int) -> None:
        max_iterations = (
            addon.max_iterations if addon.max_iterations is not None else DEFAULT_MAX_ITERATIONS
        )
        generate_summaries = (
            addon.generate_intermediate_research_summaries
            if addon.generate_intermediate_research_summaries is not None
            else False
        )
        num_parents = addon.num_parents if addon.num_parents is not None else DEFAULT_NUM_PARENTS
        num_extra_scores = addon.num_extra_scores if addon.num_extra_scores is not None else DEFAULT_NUM_EXTRA_SCORES
        rescore_interval = addon.rescore_interval if addon.rescore_interval is not None else DEFAULT_RESCORE_INTERVAL
        num_executions_per_iteration = addon.num_executions_per_iteration if addon.num_executions_per_iteration is not None else DEFAULT_NUM_EXECUTIONS_PER_ITERATION
        execution_cost = addon.execution_cost if addon.execution_cost is not None else DEFAULT_EXECUTION_COST
        branch_prob = addon.branch_prob if addon.branch_prob is not None else DEFAULT_BRANCH_PROB
        num_interpretations = addon.num_interpretations if addon.num_interpretations is not None else DEFAULT_NUM_INTERPRETATIONS

        num_proposals = addon.num_proposals if addon.num_proposals is not None else DEFAULT_NUM_PROPOSALS

        run_evolve_solution_loop(
            task=task,
            run_step=run_step,
            max_iterations=max_iterations,
            num_proposals=num_proposals,
            num_interpretations=num_interpretations,
            num_parents=num_parents,
            num_extra_scores=num_extra_scores,
            rescore_interval=rescore_interval,
            num_executions_per_iteration=num_executions_per_iteration,
            execution_cost=execution_cost,
            branch_prob=branch_prob,
            generate_intermediate_research_summaries=generate_summaries,
            stage_prefix=f"addon-{index}-",
        )

    def get_prompt(self, addon: Addon) -> str:
        pass
