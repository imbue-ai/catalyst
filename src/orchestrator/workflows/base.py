from abc import ABC, abstractmethod
from typing import Any, Callable, List, Dict, Optional, Set
import os
import subprocess
import random
import threading
import logging
from ..models import Task, StepStatus

logger = logging.getLogger(__name__)

DEFAULT_EVOLVE_ITERATIONS = 3
DEFAULT_NUM_PARENTS = 3
DEFAULT_STREAMLINE_PROB = 0.25
DEFAULT_NUM_EXTRA_SCORES = 5


def run_context_manager(task: Task, args: List[str]) -> str:
    env = os.environ.copy()

    ctx_mgr_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "context_manager.py")
    )
    cmd = ["uv", "run", "python", ctx_mgr_path] + args
    result = subprocess.run(
        cmd,
        env=env,
        cwd=os.path.abspath(task.env_folder),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def get_step_output(task: Task, stage_prefix: str) -> Optional[Dict[str, Any]]:
    for s in task.steps:
        if s.stage == stage_prefix and s.status == StepStatus.COMPLETED:
            return s.outputs
    return None


def run_step_if_needed(
    task: Task, run_step_fn: Callable, stage: str, prompt: str
) -> Optional[Dict[str, Any]]:
    out = get_step_output(task, stage)
    if not out:
        # Check if already canceled to avoid logging "Running"
        for s in task.steps:
            if s.stage == stage and s.status == StepStatus.CANCELED:
                logger.debug(
                    f"[ORCHESTRATOR] [{task.id[:8]}] Skipping canceled step {stage}..."
                )
                return {"_canceled": True}

        logger.debug(f"[ORCHESTRATOR] [{task.id[:8]}] Running {stage}...")
        out = run_step_fn(task, stage, prompt)
    return out


def run_summarize_title(task: Task, run_step_fn: Callable, content_desc: str) -> None:
    if not task.title:
        title_data = run_step_if_needed(
            task,
            run_step_fn,
            "summarize-title",
            f"Please provide a very short, summarized title (maximum 5 words) for the following research:\n```\n{content_desc}\n```\n"
            "Return ONLY a JSON object with the key 'title'.",
        )
        if title_data and isinstance(title_data, dict):
            task.title = title_data.get("title")


def run_refinement_loop(
    task: Task,
    run_step_fn: Callable,
    theory_id: str,
    lit_review_id: Optional[str],
    apply_extensions: bool,
    max_refinements: int,
    stage_prefix: str = "",
) -> str:
    i = 1
    while i <= max_refinements:
        # Review
        review_data = run_step_if_needed(
            task,
            run_step_fn,
            f"{stage_prefix}review-theory-{i}",
            f"Please run the review-theory skill for the following theory_id: {theory_id}. "
            "When you are done, return ONLY a JSON object with the key 'review_ids' (a list of strings).",
        )

        if not review_data:
            raise Exception(f"Theory review for iteration {i} failed.")

        if review_data.get("_canceled"):
            i += 1
            continue

        review_ids = review_data.get("review_ids", [])
        if not review_ids:
            break

        # Refine
        prompt = f"Please run the refine-theory skill for the following theory_id: {theory_id}. "
        if lit_review_id:
            prompt += f"Use literature_review_id: {lit_review_id}. "
        prompt += "When you are done, return ONLY a JSON object with the keys 'theory_id' and 'major_changes' (boolean) to indicate if any major changes have been made to the theory."

        if not apply_extensions:
            prompt += "\n\nCRITICAL: Do not apply extensions."

        refine_data = run_step_if_needed(
            task, run_step_fn, f"{stage_prefix}refine-theory-{i}", prompt
        )

        if not refine_data:
            raise Exception(f"Theory refinement for iteration {i} failed.")

        if refine_data.get("_canceled"):
            i += 1
            continue

        theory_id = refine_data.get("theory_id") or theory_id
        if not refine_data.get("major_changes", True):
            break

        i += 1

    return theory_id


def run_evolve_loop(
    task: Task,
    run_step_fn: Callable,
    iterations: int,
    num_parents: int,
    streamline_prob: float,
    num_extra_scores: int,
    apply_extensions: bool = False,
    stage_prefix: str = "",
) -> None:
    for i in range(1, iterations + 1):
        logger.debug(
            f"[ORCHESTRATOR] [{task.id[:8]}] Evolve Loop Iteration {i}/{iterations}"
        )

        # 1. Sample Parents
        sample_out = run_context_manager(
            task,
            [
                "sample_theories",
                "--num_theories",
                str(num_parents),
                "--purpose",
                "mutation",
            ],
        )
        parent_ids = [tid.strip() for tid in sample_out.split(",") if tid.strip()]

        if not parent_ids:
            logger.debug(
                f"[ORCHESTRATOR] [{task.id[:8]}] No parent theories available to sample. Skipping iteration."
            )
            continue

        # 2. Mutate (Nested Parallel)
        logger.debug(
            f"[ORCHESTRATOR] [{task.id[:8]}] Mutating {len(parent_ids)} parents in parallel..."
        )
        new_theory_ids: Set[str] = set()
        mutation_errors = []
        mutation_results = {}

        def run_mutation(tid: str, idx: int):
            try:
                is_streamline = random.random() < streamline_prob
                if is_streamline:
                    stage_name = f"{stage_prefix}mutate-streamline-{i}-{idx}"
                    res = run_step_if_needed(
                        task,
                        run_step_fn,
                        stage_name,
                        f"Please run the streamline-theory-variations skill for theory_id: {tid}. "
                        "Return a JSON object with the key 'theory_ids' containing a list of the generated theory IDs.",
                    )
                    mutation_results[stage_name] = res
                else:
                    stage_name = f"{stage_prefix}mutate-refine-{i}-{idx}"
                    prompt = f"Please run the refine-theory skill for theory_id: {tid}. Return a JSON object with the key 'theory_id'."
                    if not apply_extensions:
                        prompt += "\n\nCRITICAL: Do not apply extensions."

                    res = run_step_if_needed(task, run_step_fn, stage_name, prompt)
                    mutation_results[stage_name] = res
            except Exception as e:
                mutation_errors.append(e)

        threads = []
        for idx, tid in enumerate(parent_ids):
            t = threading.Thread(target=run_mutation, args=(tid, idx))
            t.daemon = True
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if mutation_errors:
            raise mutation_errors[0]

        for res in mutation_results.values():
            if res and isinstance(res, dict) and not res.get("_canceled"):
                if "theory_ids" in res and isinstance(res["theory_ids"], list):
                    new_theory_ids.update(res["theory_ids"])
                elif "theory_id" in res:
                    new_theory_ids.add(res["theory_id"])

        new_theory_ids_list = list(new_theory_ids)

        if not new_theory_ids_list:
            logger.debug(
                f"[ORCHESTRATOR] [{task.id[:8]}] No new theories were generated. Skipping review and score."
            )
            continue

        # 3. Review (Nested Parallel)
        logger.debug(
            f"[ORCHESTRATOR] [{task.id[:8]}] Reviewing {len(new_theory_ids_list)} new theories in parallel..."
        )
        review_errors = []

        def run_review(tid: str, idx: int):
            try:
                run_step_if_needed(
                    task,
                    run_step_fn,
                    f"{stage_prefix}review-theory-{i}-{idx}",
                    f"Please run the review-theory skill for theory_id: {tid}. "
                    "Return a JSON object with the key 'review_id'.",
                )
            except Exception as e:
                review_errors.append(e)

        threads = []
        for idx, tid in enumerate(new_theory_ids_list):
            t = threading.Thread(target=run_review, args=(tid, idx))
            t.daemon = True
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if review_errors:
            raise review_errors[0]

        # 4. Sample Scoring
        score_sample_out = run_context_manager(
            task,
            [
                "sample_theories",
                "--num_theories",
                str(num_extra_scores),
                "--purpose",
                "scoring",
            ],
        )
        scoring_sample_ids = [
            tid.strip() for tid in score_sample_out.split(",") if tid.strip()
        ]

        # 5. Score Union
        union_ids = list(set(new_theory_ids_list + scoring_sample_ids))
        logger.debug(
            f"[ORCHESTRATOR] [{task.id[:8]}] Scoring {len(union_ids)} theories..."
        )
        run_step_if_needed(
            task,
            run_step_fn,
            f"{stage_prefix}score-theories-{i}",
            f"Please run the score-theories skill for the following theory_ids: {', '.join(union_ids)}. "
            "When you are done, return ONLY a JSON object mapping each theory ID to its assigned scores object (including subscores).",
        )


class Workflow(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        """Returns the structural representation of the workflow for the UI."""
        pass

    @abstractmethod
    def run(self, task: Task, run_step_fn: Callable) -> None:
        """Executes the workflow."""
        pass

    def init_db(self, task: Task) -> None:
        db_path = os.path.join(task.env_folder, ".ai-scientist-db")
        if not os.path.exists(db_path):
            logger.debug(f"[ORCHESTRATOR] [{task.id[:8]}] Initializing DB folder...")
            run_context_manager(task, ["init"])
