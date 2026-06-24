import json
import logging
import random
from typing import Any, Callable, Dict, List

from ...models import Task, StepCategory
from ...utils import run_context_manager
from ..base import (
    run_step_if_needed,
    run_local_step_if_needed,
    ParallelStepRunner,
)
from orchestrator.prompts import (
    get_propose_experiment_prompt,
    get_rank_proposals_prompt,
    get_execute_proposal_prompt,
    get_interpret_result_prompt,
    get_integrate_interpretations_prompt,
    get_score_theory_solutions_prompt,
    get_summarize_goal_progress_prompt,
)

logger = logging.getLogger(__name__)


def _sample_theories_helper(
    task: Task,
    num_theories: int,
    purpose: str,
    stage_name: str,
) -> List[Dict[str, Any]]:
    def _sample() -> Dict[str, Any]:
        out = run_context_manager(
            task,
            [
                "sample_theories",
                "--num_theories",
                str(num_theories),
                "--purpose",
                purpose,
                "--json",
            ],
        )
        try:
            samples = json.loads(out)
            return {"samples": samples}
        except Exception:
            return {"samples": []}

    res = run_local_step_if_needed(task, stage_name, _sample)
    if res and res.get("_canceled"):
        return []
    return res.get("samples", []) if res else []


def _run_interpret_results_helper(
    task: Task,
    run_step: Callable,
    stage_prefix: str,
    iteration: int,
    theory_ids: List[str],
    result_ids: List[str],
) -> bool:
    interpretation_results = {}

    def run_interpret_result(idx: int, theory_id: str):
        stage_name = f"{stage_prefix}interpret-result-{iteration}-{idx + 1}"
        res = run_step_if_needed(
            task,
            run_step,
            stage_name,
            get_interpret_result_prompt(theory_id, result_ids),
            StepCategory.THEORY_WRITING,
        )
        interpretation_results[idx] = res

    with ParallelStepRunner() as runner:
        for idx, theory_id in enumerate(theory_ids):
            runner.add(run_interpret_result, idx, theory_id)

    # Check if any interpret-result step was canceled
    for idx in range(len(theory_ids)):
        res = interpretation_results.get(idx)
        if res and res.get("_canceled"):
            return False
    return True


def build_evolve_solution_loop_structure(
    task: Task,
    max_iterations: int,
    rescore_interval: int,
    generate_intermediate_research_summaries: bool,
    stage_prefix: str = "",
) -> Dict[str, Any]:
    if max_iterations <= 0:
        return {}

    iteration_structures = {}
    for i in range(1, max_iterations + 1):
        is_mutation_iteration = i % rescore_interval == 0 or i == max_iterations

        if not is_mutation_iteration:
            propose_stages = [
                s.stage
                for s in task.steps
                if s.stage.startswith(f"{stage_prefix}propose-experiment-{i}-")
            ]

            execute_stages = [
                s.stage
                for s in task.steps
                if s.stage.startswith(f"{stage_prefix}execute-proposal-{i}-")
            ]

            interpret_stages = [
                s.stage
                for s in task.steps
                if s.stage.startswith(f"{stage_prefix}interpret-result-{i}-")
            ]

            iter_struct = [
                {"type": "step", "stage": f"{stage_prefix}sample-proposals-{i}"},
                {
                    "type": "parallel",
                    "name": "Propose Experiments",
                    "stages": propose_stages,
                },
                {"type": "step", "stage": f"{stage_prefix}rank-proposals-{i}"},
                {
                    "type": "parallel",
                    "name": "Execute Proposals",
                    "stages": execute_stages,
                },
                {"type": "step", "stage": f"{stage_prefix}sample-interpretations-{i}"},
                {
                    "type": "parallel",
                    "name": "Interpret Results",
                    "stages": interpret_stages,
                },
            ]
        else:
            integrate_stages = [
                s.stage
                for s in task.steps
                if s.stage.startswith(f"{stage_prefix}integrate-interpretations-{i}-")
            ]

            propose_solution_stages = [
                s.stage
                for s in task.steps
                if s.stage.startswith(f"{stage_prefix}propose-solution-always-{i}-")
            ]

            execute_solution_stages = [
                s.stage
                for s in task.steps
                if s.stage.startswith(f"{stage_prefix}execute-solution-candidate-{i}-")
            ]

            interpret_stages = [
                s.stage
                for s in task.steps
                if s.stage.startswith(f"{stage_prefix}interpret-result-{i}-")
            ]

            iter_struct = [
                {
                    "type": "step",
                    "stage": f"{stage_prefix}sample-integrate-parents-{i}",
                },
                {
                    "type": "parallel",
                    "name": "Integrate Interpretations",
                    "stages": integrate_stages,
                },
                {
                    "type": "parallel",
                    "name": "Propose Solution Candidates",
                    "stages": propose_solution_stages,
                },
                {
                    "type": "parallel",
                    "name": "Execute Solution Candidates",
                    "stages": execute_solution_stages,
                },
                {"type": "step", "stage": f"{stage_prefix}sample-interpretations-{i}"},
                {
                    "type": "parallel",
                    "name": "Interpret Results",
                    "stages": interpret_stages,
                },
                {"type": "step", "stage": f"{stage_prefix}sample-scoring-{i}"},
                {"type": "step", "stage": f"{stage_prefix}score-theory-solutions-{i}"},
            ]

            if generate_intermediate_research_summaries or i == max_iterations:
                iter_struct.append(
                    {
                        "type": "step",
                        "stage": f"{stage_prefix}summarize-goal-progress-{i}",
                    }
                )

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
    max_iterations: int,
    num_proposals: int,
    num_extra_interpretations: int,
    num_parents: int,
    num_extra_scores: int,
    rescore_interval: int,
    num_executions_per_iteration: int,
    execution_cost: int,
    branch_prob: float,
    generate_intermediate_research_summaries: bool,
    stage_prefix: str = "",
) -> None:

    for i in range(1, max_iterations + 1):
        logger.debug(
            f"[ORCHESTRATOR] [{task.id[:8]}] Evolve Solution Loop Iteration {i}/{max_iterations}"
        )

        is_mutation_iteration = i % rescore_interval == 0 or i == max_iterations

        if not is_mutation_iteration:
            # --- REGULAR ITERATION ---

            # 1. Sample proposals
            proposal_theories = _sample_theories_helper(
                task=task,
                num_theories=num_proposals,
                purpose="proposals",
                stage_name=f"{stage_prefix}sample-proposals-{i}",
            )
            proposal_theory_ids = [
                p.get("id") for p in proposal_theories if p.get("id")
            ]

            if not proposal_theory_ids:
                logger.warning(
                    f"[ORCHESTRATOR] [{task.id[:8]}] No theories sampled for proposals in iteration {i}. Skipping iteration."
                )
                continue

            # 2. Propose Experiments (in parallel)
            proposal_results = {}

            def run_propose_experiment(idx: int, theory_id: str):
                stage_name = f"{stage_prefix}propose-experiment-{i}-{idx + 1}"
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
                proposal_results[idx] = res

            with ParallelStepRunner() as runner:
                for idx, theory_id in enumerate(proposal_theory_ids):
                    runner.add(run_propose_experiment, idx, theory_id)

            # Check if any propose-experiment step was canceled
            is_canceled = False
            for idx in range(len(proposal_theory_ids)):
                res = proposal_results.get(idx)
                if res and res.get("_canceled"):
                    is_canceled = True
                    break
            if is_canceled:
                continue

            # Extract proposal IDs
            curr_proposal_ids = []
            for idx in range(len(proposal_theory_ids)):
                res = proposal_results.get(idx)
                p_id = res.get("proposal_id") if res else None
                curr_proposal_ids.append(p_id)

            if len(curr_proposal_ids) != len(proposal_theory_ids) or any(
                p is None for p in curr_proposal_ids
            ):
                raise Exception(
                    f"Failed to generate all {len(proposal_theory_ids)} proposals in iteration {i}."
                )

            # 3. Rank the proposals and select the proposals to execute
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
                logger.info(
                    "Selected proposals list is empty. Skipping to interpretation."
                )
                continue

            # Execute Proposals (in parallel)
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

            # Extract result IDs
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

            # 4. Sample interpretations
            interpret_theories = _sample_theories_helper(
                task=task,
                num_theories=num_extra_interpretations,
                purpose="interpret_results",
                stage_name=f"{stage_prefix}sample-interpretations-{i}",
            )
            interpret_theory_ids = [
                p.get("id") for p in interpret_theories if p.get("id")
            ]

            unioned_theory_ids = sorted(
                list(set(interpret_theory_ids + proposal_theory_ids))
            )

            # Run interpret-result helper
            success = _run_interpret_results_helper(
                task=task,
                run_step=run_step,
                stage_prefix=stage_prefix,
                iteration=i,
                theory_ids=unioned_theory_ids,
                result_ids=result_ids,
            )
            if not success:
                continue

        else:
            # --- MUTATION ITERATION ---

            # A. Sample integration parents
            integrate_parents = _sample_theories_helper(
                task=task,
                num_theories=num_parents,
                purpose="integration",
                stage_name=f"{stage_prefix}sample-integrate-parents-{i}",
            )
            integrate_parent_ids = [
                p.get("id") for p in integrate_parents if p.get("id")
            ]

            if not integrate_parent_ids:
                logger.warning(
                    f"[ORCHESTRATOR] [{task.id[:8]}] No integrate parents sampled in iteration {i}. Skipping iteration."
                )
                continue

            # B. Integrate Interpretations in parallel
            integration_results = {}

            def run_integrate_interpretations(idx: int, theory_id: str):
                deterministic_rng = random.Random(
                    f"{theory_id}:{idx}:integrate-interpretations:{stage_prefix}:{i}"
                )
                create_branch = deterministic_rng.random() < branch_prob
                stage_name = f"{stage_prefix}integrate-interpretations-{i}-{idx + 1}"
                res = run_step_if_needed(
                    task,
                    run_step,
                    stage_name,
                    get_integrate_interpretations_prompt(
                        theory_id, create_branch=create_branch
                    ),
                    StepCategory.THEORY_WRITING,
                )
                integration_results[idx] = res

            with ParallelStepRunner() as runner:
                for idx, theory_id in enumerate(integrate_parent_ids):
                    runner.add(run_integrate_interpretations, idx, theory_id)

            # Check if canceled
            is_canceled = False
            for idx in range(len(integrate_parent_ids)):
                res = integration_results.get(idx)
                if res and res.get("_canceled"):
                    is_canceled = True
                    break
            if is_canceled:
                continue

            # Extract integrated theory IDs
            integrated_theory_ids = []
            for idx in range(len(integrate_parent_ids)):
                res = integration_results.get(idx)
                t_ids = res.get("theory_ids", []) if res else []
                if isinstance(t_ids, list):
                    integrated_theory_ids.extend(t_ids)
                elif isinstance(t_ids, str):
                    integrated_theory_ids.append(t_ids)

            if not integrated_theory_ids:
                logger.warning(
                    f"[ORCHESTRATOR] [{task.id[:8]}] No integrated theory IDs returned in iteration {i}. Skipping iteration."
                )
                continue

            # C. Propose solutions ALWAYS and execute them to get solution IDs
            propose_always_results = {}

            def run_propose_always(idx: int, theory_id: str):
                stage_name = f"{stage_prefix}propose-solution-always-{i}-{idx + 1}"
                res = run_step_if_needed(
                    task,
                    run_step,
                    stage_name,
                    get_propose_experiment_prompt(theory_id, propose_solution="always"),
                    StepCategory.THEORY_WRITING,
                )
                propose_always_results[idx] = res

            with ParallelStepRunner() as runner:
                for idx, theory_id in enumerate(integrated_theory_ids):
                    runner.add(run_propose_always, idx, theory_id)

            # Check if canceled
            is_canceled = False
            for idx in range(len(integrated_theory_ids)):
                res = propose_always_results.get(idx)
                if res and res.get("_canceled"):
                    is_canceled = True
                    break
            if is_canceled:
                continue

            proposal_ids = []
            for idx in range(len(integrated_theory_ids)):
                res = propose_always_results.get(idx)
                p_id = res.get("proposal_id") if res else None
                proposal_ids.append(p_id)

            if len(proposal_ids) != len(integrated_theory_ids) or any(
                p is None for p in proposal_ids
            ):
                raise Exception(
                    f"Failed to generate all solution candidate proposals in iteration {i}."
                )

            # Execute solution candidates in parallel
            execute_always_results = {}

            def run_execute_always(idx: int, proposal_id: str):
                stage_name = f"{stage_prefix}execute-solution-candidate-{i}-{idx + 1}"
                res = run_step_if_needed(
                    task,
                    run_step,
                    stage_name,
                    get_execute_proposal_prompt(proposal_id),
                    StepCategory.MISC,
                    cost=execution_cost,
                )
                execute_always_results[idx] = res

            with ParallelStepRunner() as runner:
                for idx, proposal_id in enumerate(proposal_ids):
                    runner.add(run_execute_always, idx, proposal_id)

            # Check if execution was canceled
            is_canceled = False
            for idx in range(len(proposal_ids)):
                res = execute_always_results.get(idx)
                if res and res.get("_canceled"):
                    is_canceled = True
                    break
            if is_canceled:
                continue

            solution_theory_pairs = []
            new_solution_ids = []
            for idx, theory_id in enumerate(integrated_theory_ids):
                res = execute_always_results.get(idx)
                sol_id = res.get("solution_id") if res else None
                if not sol_id:
                    raise Exception(
                        f"execute-solution-candidate-{i}-{idx + 1} did not return solution_id. Result: {res}"
                    )
                solution_theory_pairs.append((sol_id, theory_id))
                new_solution_ids.append(sol_id)

            # D. Sample interpretations (from regular loop) and Interpret Results
            interpret_theories = _sample_theories_helper(
                task=task,
                num_theories=num_extra_interpretations,
                purpose="interpret_results",
                stage_name=f"{stage_prefix}sample-interpretations-{i}",
            )
            interpret_theory_ids = [
                p.get("id") for p in interpret_theories if p.get("id")
            ]

            unioned_theory_ids = sorted(
                list(set(interpret_theory_ids + integrated_theory_ids))
            )

            # Run interpret-result helper with new solution candidate IDs as result_ids
            success = _run_interpret_results_helper(
                task=task,
                run_step=run_step,
                stage_prefix=stage_prefix,
                iteration=i,
                theory_ids=unioned_theory_ids,
                result_ids=new_solution_ids,
            )
            if not success:
                continue

            # E. Sample scoring theories
            scoring_theories = _sample_theories_helper(
                task=task,
                num_theories=num_extra_scores,
                purpose="scoring",
                stage_name=f"{stage_prefix}sample-scoring-{i}",
            )

            # Deduplicate and build final pairs: use real solution IDs from Step C first,
            # fall back to latest_solution (if available) or placeholder for remaining sampled scoring theories.
            final_pairs = []
            seen_theories = set()

            for sol_id, theory_id in solution_theory_pairs:
                if theory_id not in seen_theories:
                    seen_theories.add(theory_id)
                    final_pairs.append((sol_id, theory_id))

            for t in scoring_theories:
                theory_id = t.get("id")
                if theory_id and theory_id not in seen_theories:
                    seen_theories.add(theory_id)
                    sol_id = t.get("latest_solution") or "placeholder"
                    final_pairs.append((sol_id, theory_id))

            # F. Run the "score-theory-solutions" skill
            score_res = run_step_if_needed(
                task,
                run_step,
                f"{stage_prefix}score-theory-solutions-{i}",
                get_score_theory_solutions_prompt(final_pairs),
                StepCategory.REVIEW,
            )
            if score_res and score_res.get("_canceled"):
                continue

            if generate_intermediate_research_summaries or i == max_iterations:
                sum_res = run_step_if_needed(
                    task,
                    run_step,
                    f"{stage_prefix}summarize-goal-progress-{i}",
                    get_summarize_goal_progress_prompt(),
                    StepCategory.MISC,
                )
                if sum_res and sum_res.get("_canceled"):
                    continue
