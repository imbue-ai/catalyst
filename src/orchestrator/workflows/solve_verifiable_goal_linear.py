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
    get_rank_experiment_proposals_prompt,
    get_execute_proposal_prompt,
    get_interpret_experiment_prompt,
    get_review_interpretations_prompt,
    get_refine_interpretations_prompt,
)

logger = logging.getLogger(__name__)


def extract_proposal_id_fallback(res: Any) -> str:
    if isinstance(res, dict):
        if "proposal_id" in res and res["proposal_id"]:
            return res["proposal_id"]
    text = str(res)
    matches = re.findall(r"\b(O_\w+)\b", text)
    if matches:
        return matches[0]
    return None


def extract_best_proposal_id(res: Any, candidate_ids: List[str]) -> str:
    if isinstance(res, dict):
        for key in ["best_proposal_id", "selected_proposal_id", "top_proposal_id"]:
            if key in res and res[key]:
                return res[key]
        if "rankings" in res and isinstance(res["rankings"], list) and res["rankings"]:
            return res["rankings"][0]
    text = str(res)
    matches = re.findall(r"\b(O_\w+)\b", text)
    for m in matches:
        if m in candidate_ids:
            return m
    return candidate_ids[0] if candidate_ids else None


def extract_experiment_id(res: Any) -> str:
    if isinstance(res, dict):
        if "experiment_id" in res and res["experiment_id"]:
            return res["experiment_id"]
    text = str(res)
    matches = re.findall(r"\b(X_\w+)\b", text)
    if matches:
        return matches[0]
    return None


def extract_interpretations_id_fallback(res: Any) -> str:
    if isinstance(res, dict):
        if "interpretations_id" in res and res["interpretations_id"]:
            return res["interpretations_id"]
    text = str(res)
    matches = re.findall(r"\b(I_\w+)\b", text)
    if matches:
        return matches[0]
    return None


def extract_review_id_fallback(res: Any) -> str:
    if isinstance(res, dict):
        if "review_id" in res and res["review_id"]:
            return res["review_id"]
    text = str(res)
    matches = re.findall(r"\b(R_\w+)\b", text)
    if matches:
        return matches[0]
    return None


class SolveVerifiableGoalLinearWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "solve-verifiable-goal-linear"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        num_strands = int(task.workflow_inputs.get("num_strands", 5))
        max_experiments = int(task.workflow_inputs.get("max_experiments", 3))

        structure = [
            {"type": "step", "stage": "summarize-title"},
            {"type": "step", "stage": "initialize-interpretations"},
        ]

        if max_experiments > 0:
            iteration_structures = {}
            for i in range(1, max_experiments + 1):
                iter_struct = [
                    {
                        "type": "parallel",
                        "name": "Propose Experiment",
                        "stages": [
                            f"propose-experiment-{i}-{j}"
                            for j in range(1, num_strands + 1)
                        ],
                    },
                    {"type": "step", "stage": f"rank-experiment-proposals-{i}"},
                    {"type": "step", "stage": f"execute-proposal-{i}"},
                    {
                        "type": "parallel",
                        "name": "Interpret Experiment",
                        "stages": [
                            f"interpret-experiment-{i}-{j}"
                            for j in range(1, num_strands + 1)
                        ],
                    },
                    {
                        "type": "parallel",
                        "name": "Review Interpretations",
                        "stages": [
                            f"review-interpretations-{i}-{j}"
                            for j in range(1, num_strands + 1)
                        ],
                    },
                    {
                        "type": "parallel",
                        "name": "Refine Interpretations",
                        "stages": [
                            f"refine-interpretations-{i}-{j}"
                            for j in range(1, num_strands + 1)
                        ],
                    },
                ]
                iteration_structures[str(i)] = iter_struct

            structure.append(
                {
                    "type": "loop",
                    "name": "Research Loop",
                    "iterations": max_experiments,
                    "iteration_structures": iteration_structures,
                }
            )

        return structure

    def run(self, task: Task, run_step: Callable) -> None:
        goal = task.workflow_inputs.get("goal")
        assert goal, "Goal is required."
        verification_instructions = task.workflow_inputs.get("verification_instructions")
        assert verification_instructions, "Verification instructions are required."

        with open(os.path.join(task.env_folder, "goal.txt"), "w") as f:
            f.write(goal.strip() + "\n")

        with open(os.path.join(task.env_folder, "verification_instructions.txt"), "w") as f:
            f.write(verification_instructions.strip() + "\n")

        # Step 0: Summarize Title
        run_summarize_title(task, run_step, f"goal: {goal}")

        # Step 1: Initialize Interpretations
        num_strands = int(task.workflow_inputs.get("num_strands", 5))

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

        max_experiments = int(task.workflow_inputs.get("max_experiments", 3))

        for i in range(1, max_experiments + 1):
            # 1. Propose Experiment (in parallel for each of the n interpretations log IDs)
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
                p_id = extract_proposal_id_fallback(res)
                curr_proposal_ids.append(p_id)

            if len(curr_proposal_ids) != num_strands or any(
                p is None for p in curr_proposal_ids
            ):
                raise Exception(
                    f"Failed to generate all {num_strands} proposals in iteration {i}."
                )

            # 2. Rank Experiment Proposals (sequential step)
            rank_data = run_step_if_needed(
                task,
                run_step,
                f"rank-experiment-proposals-{i}",
                get_rank_experiment_proposals_prompt(curr_proposal_ids),
                StepCategory.REVIEW,
            )

            if rank_data and rank_data.get("_canceled"):
                continue

            # Parse ranking and select the best proposal ID
            best_proposal_id = extract_best_proposal_id(rank_data, curr_proposal_ids)
            if not best_proposal_id:
                raise Exception(f"Failed to identify top proposal ID in iteration {i}.")

            # 3. Execute Proposal (sequential step)
            execute_data = run_step_if_needed(
                task,
                run_step,
                f"execute-proposal-{i}",
                get_execute_proposal_prompt(best_proposal_id),
                StepCategory.MISC,
            )

            if execute_data and execute_data.get("_canceled"):
                continue

            experiment_id = extract_experiment_id(execute_data)
            if not experiment_id:
                raise Exception(
                    f"Failed to execute proposal {best_proposal_id} in iteration {i}."
                )

            # 4. Interpret Experiment (in parallel for each of the n interpretation logs)
            interpretation_results = {}

            def run_interpret_experiment(strand_idx: int, interpretations_id: str):
                stage_name = f"interpret-experiment-{i}-{strand_idx + 1}"
                res = run_step_if_needed(
                    task,
                    run_step,
                    stage_name,
                    get_interpret_experiment_prompt(interpretations_id, experiment_id),
                    StepCategory.THEORY_WRITING,
                )
                interpretation_results[strand_idx] = res

            with ParallelStepRunner() as runner:
                for idx, interpretations_id in enumerate(interpretations_ids):
                    runner.add(run_interpret_experiment, idx, interpretations_id)

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
                new_i_id = extract_interpretations_id_fallback(res)
                new_interpretations_ids.append(new_i_id)

            if len(new_interpretations_ids) != num_strands or any(
                x is None for x in new_interpretations_ids
            ):
                raise Exception(
                    f"Failed to generate all {num_strands} interpretations in iteration {i}."
                )

            # Update working interpretations IDs
            interpretations_ids = new_interpretations_ids

            # 5. Review Interpretations (in parallel for each of the n interpretations log IDs)
            review_results = {}

            def run_review_interpretations(strand_idx: int, interpretations_id: str):
                stage_name = f"review-interpretations-{i}-{strand_idx + 1}"
                res = run_step_if_needed(
                    task,
                    run_step,
                    stage_name,
                    get_review_interpretations_prompt(interpretations_id),
                    StepCategory.REVIEW,
                )
                review_results[strand_idx] = res

            with ParallelStepRunner() as runner:
                for idx, interpretations_id in enumerate(interpretations_ids):
                    runner.add(run_review_interpretations, idx, interpretations_id)

            is_canceled = False
            for idx in range(num_strands):
                res = review_results.get(idx)
                if res and res.get("_canceled"):
                    is_canceled = True
                    break
            if is_canceled:
                continue

            # Extract review IDs
            review_ids = []
            for idx in range(num_strands):
                res = review_results.get(idx)
                r_id = extract_review_id_fallback(res)
                review_ids.append(r_id)

            if len(review_ids) != num_strands or any(r is None for r in review_ids):
                raise Exception(
                    f"Failed to generate all {num_strands} reviews in iteration {i}."
                )

            # 6. Refine Interpretations (in parallel for each of the n interpretations log IDs)
            refinement_results = {}

            def run_refine_interpretations(
                strand_idx: int, interpretations_id: str, review_id: str
            ):
                stage_name = f"refine-interpretations-{i}-{strand_idx + 1}"
                res = run_step_if_needed(
                    task,
                    run_step,
                    stage_name,
                    get_refine_interpretations_prompt(interpretations_id, review_id),
                    StepCategory.THEORY_WRITING,
                )
                refinement_results[strand_idx] = res

            with ParallelStepRunner() as runner:
                for idx in range(num_strands):
                    runner.add(
                        run_refine_interpretations,
                        idx,
                        interpretations_ids[idx],
                        review_ids[idx],
                    )

            is_canceled = False
            for idx in range(num_strands):
                res = refinement_results.get(idx)
                if res and res.get("_canceled"):
                    is_canceled = True
                    break
            if is_canceled:
                continue

            # Extract refined interpretations log IDs
            refined_interpretations_ids = []
            for idx in range(num_strands):
                res = refinement_results.get(idx)
                ref_i_id = extract_interpretations_id_fallback(res)
                refined_interpretations_ids.append(ref_i_id)

            if len(refined_interpretations_ids) != num_strands or any(
                x is None for x in refined_interpretations_ids
            ):
                raise Exception(
                    f"Failed to generate all {num_strands} refined interpretations in iteration {i}."
                )

            # Update interpretations log IDs for the next iteration
            interpretations_ids = refined_interpretations_ids
