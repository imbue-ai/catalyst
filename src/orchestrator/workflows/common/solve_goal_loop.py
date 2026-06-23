import logging
from typing import Any, Callable, List, Dict

from ...models import Task, StepCategory
from ..base import (
    run_step_if_needed,
    ParallelStepRunner,
)
from orchestrator.prompts import (
    get_propose_experiment_prompt,
    get_rank_proposals_prompt,
    get_execute_proposal_prompt,
    get_interpret_result_prompt,
    get_integrate_interpretations_prompt,
)

logger = logging.getLogger(__name__)


def build_solve_goal_loop_structure(
    task: Task,
    num_strands: int,
    max_iterations: int,
    integration_interval: int,
    stage_prefix: str = "",
) -> Dict[str, Any]:
    if max_iterations <= 0:
        return {}

    iteration_structures = {}
    for i in range(1, max_iterations + 1):
        execute_stages = [
            s.stage
            for s in task.steps
            if s.stage.startswith(f"{stage_prefix}execute-proposal-{i}-")
        ]

        iter_struct = [
            {
                "type": "parallel",
                "name": "Propose Experiments",
                "stages": [
                    f"{stage_prefix}propose-experiment-{i}-{j}"
                    for j in range(1, num_strands + 1)
                ],
            },
            {"type": "step", "stage": f"{stage_prefix}rank-proposals-{i}"},
            {
                "type": "parallel",
                "name": "Execute Proposals",
                "stages": execute_stages,
            },
            {
                "type": "parallel",
                "name": "Interpret Results",
                "stages": [
                    f"{stage_prefix}interpret-result-{i}-{j}"
                    for j in range(1, num_strands + 1)
                ],
            },
        ]

        if i % integration_interval == 0:
            iter_struct.append(
                {
                    "type": "parallel",
                    "name": "Integrate Interpretations",
                    "stages": [
                        f"{stage_prefix}integrate-interpretations-{i}-{j}"
                        for j in range(1, num_strands + 1)
                    ],
                }
            )

        iteration_structures[str(i)] = iter_struct

    return {
        "type": "loop",
        "name": "Solve Goal Loop",
        "iterations": max_iterations,
        "iteration_structures": iteration_structures,
    }


def run_solve_goal_loop(
    task: Task,
    run_step: Callable,
    theory_ids: List[str],
    max_iterations: int,
    num_executions_per_iteration: int,
    execution_cost: int,
    integration_interval: int,
    stage_prefix: str = "",
) -> List[str]:
    num_strands = len(theory_ids)

    for i in range(1, max_iterations + 1):
        # 1. Propose Experiments (in parallel for each of the n theory IDs)
        proposal_results = {}

        def run_propose_experiment(strand_idx: int, theory_id: str):
            stage_name = f"{stage_prefix}propose-experiment-{i}-{strand_idx + 1}"
            propose_solution = "always" if i == max_iterations else None
            res = run_step_if_needed(
                task,
                run_step,
                stage_name,
                get_propose_experiment_prompt(
                    theory_id, propose_solution=propose_solution
                ),
                StepCategory.THEORY_WRITING,
            )
            proposal_results[strand_idx] = res

        with ParallelStepRunner() as runner:
            for idx, theory_id in enumerate(theory_ids):
                runner.add(run_propose_experiment, idx, theory_id)

        # Check if any propose-experiment step was canceled
        is_canceled = False
        for idx in range(num_strands):
            res = proposal_results.get(idx)
            if res and res.get("_canceled"):
                is_canceled = True
                break
        if is_canceled:
            continue

        # Extract proposal IDs
        curr_proposal_ids = []
        for idx in range(num_strands):
            res = proposal_results.get(idx)
            p_id = res.get("proposal_id") if res else None
            curr_proposal_ids.append(p_id)

        if len(curr_proposal_ids) != num_strands or any(
            p is None for p in curr_proposal_ids
        ):
            raise Exception(
                f"Failed to generate all {num_strands} proposals in iteration {i}."
            )

        # 2. Rank Proposals (sequential step)
        rank_data = run_step_if_needed(
            task,
            run_step,
            f"{stage_prefix}rank-proposals-{i}",
            get_rank_proposals_prompt(curr_proposal_ids),
            StepCategory.REVIEW,
        )

        if rank_data and rank_data.get("_canceled"):
            continue

        # Parse rankings and solution candidates
        rankings = rank_data.get("rankings") if rank_data else None
        if rankings is None or not isinstance(rankings, list):
            raise Exception(
                f"rank-proposals failed to return a list of rankings in iteration {i}."
            )
        solution_candidates = (
            rank_data.get("solution_candidates") if rank_data else None
        )
        if solution_candidates is None or not isinstance(solution_candidates, list):
            raise Exception(
                f"rank-proposals failed to return a list of solution_candidates in iteration {i}."
            )

        # Merge top standard rankings with all solution candidates, removing duplicates preserving order
        seen = set()
        selected_proposals = []
        for p in rankings[:num_executions_per_iteration] + solution_candidates:
            if p not in seen:
                seen.add(p)
                selected_proposals.append(p)

        if not selected_proposals:
            logger.info("Selected proposals list is empty. Completing workflow.")
            return theory_ids

        # 3. Execute Proposals (parallel step)
        execute_results = {}

        def run_execute_proposal(prop_idx: int, proposal_id: str):
            stage_name = f"{stage_prefix}execute-proposal-{i}-{prop_idx + 1}"
            res = run_step_if_needed(
                task,
                run_step,
                stage_name,
                get_execute_proposal_prompt(proposal_id),
                StepCategory.MISC,
                cost=execution_cost,
            )
            execute_results[prop_idx] = res

        with ParallelStepRunner() as runner:
            for idx, proposal_id in enumerate(selected_proposals):
                runner.add(run_execute_proposal, idx, proposal_id)

        # Check if any execute-proposal step was canceled
        is_canceled = False
        for idx in range(len(selected_proposals)):
            res = execute_results.get(idx)
            if res and res.get("_canceled"):
                is_canceled = True
                break
        if is_canceled:
            continue

        # Extract result IDs (experiment_id, literature_id, or solution_id)
        result_ids = []
        for idx in range(len(selected_proposals)):
            res = execute_results.get(idx)
            if res:
                ret_id = (
                    res.get("experiment_id")
                    or res.get("literature_id")
                    or res.get("solution_id")
                )
                if ret_id:
                    result_ids.append(ret_id)
                else:
                    raise Exception(
                        f"execute-proposal-{i}-{idx + 1} did not return experiment_id, literature_id, or solution_id. Result: {res}"
                    )
            else:
                raise Exception(
                    f"Failed to execute proposal {selected_proposals[idx]} in iteration {i}."
                )

        # 4. Interpret Results (in parallel for each of the n theories)
        interpretation_results = {}

        def run_interpret_result(strand_idx: int, theory_id: str):
            stage_name = f"{stage_prefix}interpret-result-{i}-{strand_idx + 1}"
            res = run_step_if_needed(
                task,
                run_step,
                stage_name,
                get_interpret_result_prompt(theory_id, result_ids),
                StepCategory.THEORY_WRITING,
            )
            interpretation_results[strand_idx] = res

        with ParallelStepRunner() as runner:
            for idx, theory_id in enumerate(theory_ids):
                runner.add(run_interpret_result, idx, theory_id)

        is_canceled = False
        for idx in range(num_strands):
            res = interpretation_results.get(idx)
            if res and res.get("_canceled"):
                is_canceled = True
                break
        if is_canceled:
            continue

        # Extract new theory IDs
        new_theory_ids = []
        for idx in range(num_strands):
            res = interpretation_results.get(idx)
            new_t_id = res.get("theory_id") if res else None
            new_theory_ids.append(new_t_id)

        if len(new_theory_ids) != num_strands or any(x is None for x in new_theory_ids):
            raise Exception(
                f"Failed to generate all {num_strands} theories in iteration {i}."
            )

        # 5. Integrate Interpretations (conditionally every integration_interval-th iteration)
        if i % integration_interval == 0:
            integration_results = {}

            def run_integrate_interpretations(strand_idx: int, theory_id: str):
                stage_name = (
                    f"{stage_prefix}integrate-interpretations-{i}-{strand_idx + 1}"
                )
                res = run_step_if_needed(
                    task,
                    run_step,
                    stage_name,
                    get_integrate_interpretations_prompt(theory_id),
                    StepCategory.THEORY_WRITING,
                )
                integration_results[strand_idx] = res

            with ParallelStepRunner() as runner:
                for idx, theory_id in enumerate(new_theory_ids):
                    runner.add(run_integrate_interpretations, idx, theory_id)

            is_canceled = False
            for idx in range(num_strands):
                res = integration_results.get(idx)
                if res and res.get("_canceled"):
                    is_canceled = True
                    break
            if is_canceled:
                continue

            integrated_theory_ids = []
            for idx in range(num_strands):
                res = integration_results.get(idx)
                integrated_t_ids = res.get("theory_ids", []) if res else []
                integrated_theory_ids.extend(integrated_t_ids)

            if len(integrated_theory_ids) != num_strands:
                raise Exception(
                    f"Failed to integrate all {num_strands} interpretations in iteration {i}."
                )

            # Update working theory IDs directly for the next iteration using integrated theories
            theory_ids = integrated_theory_ids
        else:
            # Update working theory IDs directly for the next iteration using interpreted theories
            theory_ids = new_theory_ids

    return theory_ids
