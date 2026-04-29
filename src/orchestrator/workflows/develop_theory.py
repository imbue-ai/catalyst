import threading
from typing import Any, Callable, List, Dict
from ..models import Task
from .base import Workflow, get_step_output, run_step_if_needed, run_evolve_loop


class DevelopTheoryWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "develop-theory"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        structure = [
            {"type": "step", "stage": "summarize-title"},
            {
                "type": "parallel",
                "name": "Gather Context",
                "stages": ["literature-review", "explore"],
            },
            {"type": "step", "stage": "write-n-theories"},
        ]

        review_stages = [
            s.stage
            for s in task.steps
            if s.stage.startswith("review-theory-") and len(s.stage.split("-")) == 3
        ]
        if review_stages:
            structure.append(
                {"type": "parallel", "name": "Review Theories", "stages": review_stages}
            )

        if any(s.stage == "score-theories" for s in task.steps):
            structure.append({"type": "step", "stage": "score-theories"})

        evolve_iterations = int(task.workflow_inputs.get("evolve_iterations", 0))
        if evolve_iterations > 0:
            iteration_structures = {}
            for i in range(1, evolve_iterations + 1):
                iter_struct = []

                # Mutate parallel block
                mutate_stages = [
                    s.stage
                    for s in task.steps
                    if s.stage.startswith(f"mutate-streamline-{i}-")
                    or s.stage.startswith(f"mutate-refine-{i}-")
                ]
                iter_struct.append(
                    {"type": "parallel", "name": "Mutate", "stages": mutate_stages}
                )

                # Review parallel block
                loop_review_stages = [
                    s.stage
                    for s in task.steps
                    if s.stage.startswith(f"review-theory-{i}-")
                ]
                iter_struct.append(
                    {"type": "parallel", "name": "Review", "stages": loop_review_stages}
                )

                # Score step
                iter_struct.append({"type": "step", "stage": f"score-theories-{i}"})

                iteration_structures[str(i)] = iter_struct

            structure.append(
                {
                    "type": "loop",
                    "name": "Evolve Theories",
                    "iterations": evolve_iterations,
                    "iteration_structures": iteration_structures,
                }
            )

        return structure

    def run(self, task: Task, run_step: Callable) -> None:
        self.init_db(task)

        # Step 0: Summarize Title
        if not task.title:
            title_data = run_step_if_needed(
                task,
                run_step,
                "summarize-title",
                f"Please provide a very short, summarized title (maximum 5 words) for the following research phenomenon: {task.workflow_inputs.get('phenomenon')}. "
                "Return a JSON object with the key 'title'.",
            )
            if title_data and isinstance(title_data, dict):
                task.title = title_data.get("title")

        # Step 1 & 2: Literature Review and Exploration in Parallel
        lit_out = get_step_output(task, "literature-review")
        lit_review_id = lit_out.get("literature_review_id") if lit_out else None

        exp_out = get_step_output(task, "explore")
        exploration_id = exp_out.get("exploration_id") if exp_out else None

        if not lit_review_id or not exploration_id:
            print(
                f"[ORCHESTRATOR] [{task.id[:8]}] Running Literature Review and Exploration in parallel..."
            )
            results = {}
            errors = []

            def run_and_store(stage, prompt, key):
                try:
                    results[key] = run_step(task, stage, prompt)
                except Exception as e:
                    errors.append(e)

            threads = []
            if not lit_review_id:
                t = threading.Thread(
                    target=run_and_store,
                    args=(
                        "literature-review",
                        f"Please run the literature-review skill for the following phenomenon:\n```\n{task.workflow_inputs.get('phenomenon')}\n```\n"
                        "When you are done, return a JSON object with the key 'literature_review_id'.",
                        "lit",
                    ),
                )
                t.daemon = True
                threads.append(t)

            if not exploration_id:
                t = threading.Thread(
                    target=run_and_store,
                    args=(
                        "explore",
                        f"Please run the explore skill for the following phenomenon:\n```\n{task.workflow_inputs.get('phenomenon')}\n```\n"
                        "When you are done, return a JSON object with the key 'exploration_id'.",
                        "exp",
                    ),
                )
                t.daemon = True
                threads.append(t)

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            if errors:
                raise errors[0]

            for res in results.values():
                if res and isinstance(res, dict):
                    if "literature_review_id" in res:
                        lit_review_id = res["literature_review_id"]
                    if "exploration_id" in res:
                        exploration_id = res["exploration_id"]

        # Step 3: Write N Theories
        num_theories = task.workflow_inputs.get("num_root_theories", 3)
        theories_data = run_step_if_needed(
            task,
            run_step,
            "write-n-theories",
            f"Please run the write-n-theories skill to generate {num_theories} theories for the following phenomenon:\n```\n{task.workflow_inputs.get('phenomenon')}\n```\n"
            f"Use exploration_id: {exploration_id} and literature_review_id: {lit_review_id}. "
            "When you are done, return a JSON object with the key 'theory_ids' containing a list of the generated theory IDs.",
        )

        theory_ids = theories_data.get("theory_ids") if theories_data else None
        if not theory_ids and not (theories_data and theories_data.get("_canceled")):
            raise Exception("Theory generation failed to return theory IDs.")

        if theory_ids and isinstance(theory_ids, list):
            # Step 4: Parallel Review Theories
            print(
                f"[ORCHESTRATOR] [{task.id[:8]}] Running {len(theory_ids)} Review Theories in parallel..."
            )
            review_results = {}
            review_errors = []

            def run_review(tid):
                try:
                    review_stage = f"review-theory-{tid}"
                    res = run_step_if_needed(
                        task,
                        run_step,
                        review_stage,
                        f"Please run the review-theory skill for theory_id: {tid}. "
                        "When you are done, return a JSON object with the key 'review_id'.",
                    )
                    review_results[tid] = res
                except Exception as e:
                    review_errors.append(e)

            threads = []
            for tid in theory_ids:
                t = threading.Thread(target=run_review, args=(tid,))
                t.daemon = True
                threads.append(t)

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            if review_errors:
                raise review_errors[0]

            # Step 5: Score Theories
            score_data = run_step_if_needed(
                task,
                run_step,
                "score-theories",
                f"Please run the score-theories skill for the following theory_ids: {', '.join(theory_ids)}. "
                "When you are done, return a JSON object mapping each theory ID to its assigned score.",
            )

            # Step 6: Evolve Loop
            evolve_iterations = int(task.workflow_inputs.get("evolve_iterations", DEFAULT_EVOLVE_ITERATIONS))
            if evolve_iterations > 0:
                num_parents = int(task.workflow_inputs.get("num_parents", DEFAULT_NUM_PARENTS))
                streamline_prob = float(task.workflow_inputs.get("streamline_prob", DEFAULT_STREAMLINE_PROB))
                num_extra_scores = int(task.workflow_inputs.get("num_extra_scores", DEFAULT_NUM_EXTRA_SCORES))
                run_evolve_loop(
                    task,
                    run_step,
                    iterations=evolve_iterations,
                    num_parents=num_parents,
                    streamline_prob=streamline_prob,
                    num_extra_scores=num_extra_scores,
                )
