import random
import threading
import logging
from typing import Any, Callable, Dict, List, Optional, Set
from ...models import Task
from ...utils import run_context_manager
from ..base import run_step_if_needed, run_local_step_if_needed
from orchestrator.prompts import (
    get_review_theory_prompt,
    get_refine_theory_prompt,
    get_streamline_theory_prompt,
    get_score_theories_prompt,
    get_write_different_theory_prompt,
)
from .constants import FORCE_EXPANSION_PROB

logger = logging.getLogger(__name__)


def build_evolve_loop_structure(
    task: Task, evolve_iterations: int, stage_prefix: str = ""
) -> List[Dict[str, Any]]:
    iteration_structures = {}
    for i in range(1, evolve_iterations + 1):
        iter_struct = []

        # Sample Parents step
        iter_struct.append({"type": "step", "stage": f"{stage_prefix}sample-parents-{i}"})

        # Mutate parallel block
        mutate_stages = [
            s.stage
            for s in task.steps
            if s.stage.startswith(f"{stage_prefix}mutate-streamline-{i}-")
            or s.stage.startswith(f"{stage_prefix}mutate-refine-{i}-")
            or s.stage.startswith(f"{stage_prefix}mutate-write-different-{i}-")
        ]
        iter_struct.append(
            {"type": "parallel", "name": "Mutate", "stages": mutate_stages}
        )

        # Review parallel block
        loop_review_stages = [
            s.stage
            for s in task.steps
            if s.stage.startswith(f"{stage_prefix}review-theory-{i}-")
        ]
        iter_struct.append(
            {"type": "parallel", "name": "Review", "stages": loop_review_stages}
        )

        # Sample Scoring step
        iter_struct.append({"type": "step", "stage": f"{stage_prefix}sample-scoring-{i}"})

        # Score step
        iter_struct.append({"type": "step", "stage": f"{stage_prefix}score-theories-{i}"})

        iteration_structures[str(i)] = iter_struct

    return [
        {
            "type": "loop",
            "name": "Evolve Theories",
            "iterations": evolve_iterations,
            "iteration_structures": iteration_structures,
        }
    ]


def run_evolve_loop(
    task: Task,
    run_step_fn: Callable,
    iterations: int,
    num_parents: int,
    max_streamline_prob: float,
    write_different_prob: float,
    num_extra_scores: int,
    apply_expansions: Optional[str] = None,
    lit_review_id: Optional[str] = None,
    stage_prefix: str = "",
) -> None:
    for i in range(1, iterations + 1):
        logger.debug(
            f"[ORCHESTRATOR] [{task.id[:8]}] Evolve Loop Iteration {i}/{iterations}"
        )

        # 1. Sample Parents
        def _sample_parents() -> Dict[str, Any]:
            out = run_context_manager(
                task,
                [
                    "sample_theories",
                    "--num_theories",
                    str(num_parents),
                    "--purpose",
                    "mutation",
                    "--json",
                ],
            )
            import json

            try:
                samples = json.loads(out)
                return {"parents": samples}
            except Exception:
                return {"parents": []}

        sample_res = run_local_step_if_needed(
            task, f"{stage_prefix}sample-parents-{i}", _sample_parents
        )
        if sample_res and sample_res.get("_canceled"):
            continue

        parents = sample_res.get("parents", []) if sample_res else []
        parents = sorted(parents, key=lambda p: p.get("id", ""))

        if not parents:
            logger.debug(
                f"[ORCHESTRATOR] [{task.id[:8]}] No parent theories available to sample. Skipping iteration."
            )
            continue

        # 2. Mutate (Nested Parallel)
        logger.debug(
            f"[ORCHESTRATOR] [{task.id[:8]}] Mutating {len(parents)} parents in parallel..."
        )
        new_theory_ids: Set[str] = set()
        mutation_errors = []
        mutation_results = {}

        def run_mutation(parent: dict, idx: int):
            try:
                tid = parent.get("id", "")
                deterministic_rng = random.Random(f"{tid}:{idx}:{stage_prefix}:{i}")
                length_score = parent.get("subscores", {}).get("length", 0.0)
                streamline_prob = max_streamline_prob * (1.0 - length_score)
                rng_val = deterministic_rng.random()
                if rng_val < streamline_prob:
                    stage_name = f"{stage_prefix}mutate-streamline-{i}-{idx}"
                    res = run_step_if_needed(
                        task,
                        run_step_fn,
                        stage_name,
                        get_streamline_theory_prompt(tid),
                    )
                    mutation_results[stage_name] = res
                elif rng_val < streamline_prob + write_different_prob:
                    stage_name = f"{stage_prefix}mutate-write-different-{i}-{idx}"
                    parent_ids = [p.get("id", "") for p in parents]
                    res = run_step_if_needed(
                        task,
                        run_step_fn,
                        stage_name,
                        get_write_different_theory_prompt(
                            parent_ids, lit_review_id=lit_review_id
                        ),
                    )
                    mutation_results[stage_name] = res
                else:
                    if apply_expansions is None:
                        # Force expansion with some probability
                        apply_expansions_for_mutation = (
                            "always"
                            if (deterministic_rng.random() < FORCE_EXPANSION_PROB)
                            else apply_expansions
                        )
                    else:
                        apply_expansions_for_mutation = apply_expansions
                    stage_name = f"{stage_prefix}mutate-refine-{i}-{idx}"
                    res = run_step_if_needed(
                        task,
                        run_step_fn,
                        stage_name,
                        get_refine_theory_prompt(
                            tid,
                            apply_expansions=apply_expansions_for_mutation,
                            lit_review_id=lit_review_id,
                        ),
                    )
                    mutation_results[stage_name] = res
            except Exception as e:
                mutation_errors.append(e)

        threads = []
        for idx, parent in enumerate(parents):
            t = threading.Thread(target=run_mutation, args=(parent, idx))
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
                elif "theory_id" in res and isinstance(res["theory_id"], str):
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
                    get_review_theory_prompt(tid),
                    cost=3,
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
        def _sample_scoring() -> Dict[str, Any]:
            out = run_context_manager(
                task,
                [
                    "sample_theories",
                    "--num_theories",
                    str(num_extra_scores),
                    "--purpose",
                    "scoring",
                    "--json",
                ],
            )
            import json

            try:
                samples = json.loads(out)
                return {"scoring_ids": [s["id"] for s in samples]}
            except Exception:
                return {"scoring_ids": []}

        score_sample_res = run_local_step_if_needed(
            task, f"{stage_prefix}sample-scoring-{i}", _sample_scoring
        )
        if score_sample_res and score_sample_res.get("_canceled"):
            continue

        scoring_sample_ids = (
            score_sample_res.get("scoring_ids", []) if score_sample_res else []
        )

        # 5. Score Union
        union_ids = list(set(new_theory_ids_list + scoring_sample_ids))
        logger.debug(
            f"[ORCHESTRATOR] [{task.id[:8]}] Scoring {len(union_ids)} theories..."
        )
        run_step_if_needed(
            task,
            run_step_fn,
            f"{stage_prefix}score-theories-{i}",
            get_score_theories_prompt(union_ids),
        )
