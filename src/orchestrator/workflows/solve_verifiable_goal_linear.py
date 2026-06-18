import logging
import os
import re
import tempfile
from typing import Any, Callable, List, Dict

from ..models import Task, StepCategory
from ..utils import run_context_manager
from .base import (
    Workflow,
    run_step_if_needed,
    run_local_step_if_needed,
    ParallelStepRunner,
)
from .common import run_summarize_title
from orchestrator.prompts import (
    get_propose_experiment_prompt,
    get_rank_proposals_prompt,
    get_execute_proposal_prompt,
    get_interpret_result_prompt,
)

logger = logging.getLogger(__name__)


class SolveVerifiableGoalLinearWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "solve-verifiable-goal-linear"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        num_strands = int(task.workflow_inputs.get("num_strands", 3))
        max_iterations = int(task.workflow_inputs.get("max_iterations", 10))

        structure = [
            {"type": "step", "stage": "summarize-title"},
            {"type": "step", "stage": "initialize-interpretations"},
        ]

        if max_iterations > 0:
            iteration_structures = {}
            for i in range(1, max_iterations + 1):
                execute_stages = [
                    s.stage
                    for s in task.steps
                    if s.stage.startswith(f"execute-proposal-{i}-")
                ]
                interpret_stages = [
                    s.stage
                    for s in task.steps
                    if s.stage.startswith(f"interpret-result-{i}-")
                ]

                iter_struct = [
                    {
                        "type": "parallel",
                        "name": "Propose Experiments",
                        "stages": [
                            f"propose-experiment-{i}-{j}"
                            for j in range(1, num_strands + 1)
                        ],
                    },
                    {"type": "step", "stage": f"rank-proposals-{i}"},
                    {
                        "type": "parallel",
                        "name": "Execute Proposals",
                        "stages": execute_stages,
                    },
                    {
                        "type": "parallel",
                        "name": "Interpret Results",
                        "stages": interpret_stages,
                    },
                ]
                iteration_structures[str(i)] = iter_struct

            structure.append(
                {
                    "type": "loop",
                    "name": "Solve Goal Loop",
                    "iterations": max_iterations,
                    "iteration_structures": iteration_structures,
                }
            )

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

        # Step 1: Initialize Interpretations
        num_strands = int(task.workflow_inputs.get("num_strands", 3))

        def _initialize_interpretations() -> Dict[str, Any]:
            abs_env_folder = os.path.abspath(task.env_folder)
            tmp_dir = os.path.join(abs_env_folder, "tmp")
            os.makedirs(tmp_dir, exist_ok=True)

            interpretations_ids = []
            for idx in range(num_strands):
                # Create unique output folder under tmp
                output_dir = tempfile.mkdtemp(
                    prefix=f"initialize-interpretations-output-strand-{idx + 1}-",
                    dir=tmp_dir,
                )

                # Create interpretations.md
                interpretations_file = os.path.join(output_dir, "interpretations.md")
                with open(interpretations_file, "w", encoding="utf-8") as f:
                    f.write(
                        "# Interpretations log\n**Research goal:** "
                        + goal.strip()
                        + "\n\n"
                    )

                # Store results using run_context_manager in a subprocess
                out = run_context_manager(
                    task,
                    [
                        "store_results",
                        "--from_agent_type",
                        "initialize-interpretations",
                        "--from_folder",
                        output_dir,
                    ],
                )

                # Extract interpretations log ID from output
                match = re.search(r"Result stored with ID: (\S+)", out)
                if not match:
                    raise Exception(f"Failed to parse stored results ID. Output: {out}")
                interpretations_ids.append(match.group(1))

            return {"interpretations_ids": interpretations_ids}

        init_data = run_local_step_if_needed(
            task,
            "initialize-interpretations",
            _initialize_interpretations,
        )

        interpretations_ids = []
        if init_data:
            interpretations_ids = init_data.get("interpretations_ids") or []

        if not interpretations_ids:
            if init_data and init_data.get("_canceled"):
                return
            raise Exception("Initialization failed to return interpretation log IDs.")

        max_iterations = int(task.workflow_inputs.get("max_iterations", 10))
        num_executions_per_iteration = int(
            task.workflow_inputs.get("num_executions_per_iteration", 1)
        )
        execution_cost = int(task.workflow_inputs.get("execution_cost", 1))

        for i in range(1, max_iterations + 1):
            # 1. Propose Experiments (in parallel for each of the n interpretations log IDs)
            proposal_results = {}

            def run_propose_experiment(strand_idx: int, interpretations_id: str):
                stage_name = f"propose-experiment-{i}-{strand_idx + 1}"
                res = run_step_if_needed(
                    task,
                    run_step,
                    stage_name,
                    get_propose_experiment_prompt(interpretations_id),
                    StepCategory.THEORY_WRITING,
                )
                proposal_results[strand_idx] = res

            with ParallelStepRunner() as runner:
                for idx, interpretations_id in enumerate(interpretations_ids):
                    runner.add(run_propose_experiment, idx, interpretations_id)

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
                f"rank-proposals-{i}",
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
                return

            # 3. Execute Proposals (parallel step)
            execute_results = {}

            def run_execute_proposal(prop_idx: int, proposal_id: str):
                stage_name = f"execute-proposal-{i}-{prop_idx + 1}"
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

            # 4. Interpret Results (in parallel for each of the n interpretation logs)
            interpretation_results = {}

            def run_interpret_result(strand_idx: int, interpretations_id: str):
                stage_name = f"interpret-result-{i}-{strand_idx + 1}"
                res = run_step_if_needed(
                    task,
                    run_step,
                    stage_name,
                    get_interpret_result_prompt(interpretations_id, result_ids),
                    StepCategory.THEORY_WRITING,
                )
                interpretation_results[strand_idx] = res

            with ParallelStepRunner() as runner:
                for idx, interpretations_id in enumerate(interpretations_ids):
                    runner.add(run_interpret_result, idx, interpretations_id)

            is_canceled = False
            for idx in range(num_strands):
                res = interpretation_results.get(idx)
                if res and res.get("_canceled"):
                    is_canceled = True
                    break
            if is_canceled:
                continue

            # Extract new interpretation log IDs
            new_interpretations_ids = []
            for idx in range(num_strands):
                res = interpretation_results.get(idx)
                new_i_id = res.get("interpretations_id") if res else None
                new_interpretations_ids.append(new_i_id)

            if len(new_interpretations_ids) != num_strands or any(
                x is None for x in new_interpretations_ids
            ):
                raise Exception(
                    f"Failed to generate all {num_strands} interpretations in iteration {i}."
                )

            # Update working interpretations IDs directly for the next iteration
            interpretations_ids = new_interpretations_ids
