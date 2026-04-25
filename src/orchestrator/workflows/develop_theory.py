import threading
from typing import Any, Callable, List, Dict
from ..models import Task, StepStatus
from .base import Workflow


class DevelopTheoryWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "develop-theory"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        # Count iterations dynamically based on steps
        max_iters = 1
        for s in task.steps:
            if s.stage.startswith("review-theory-") or s.stage.startswith(
                "refine-theory-"
            ):
                try:
                    it = int(s.stage.split("-")[-1])
                    if it > max_iters:
                        max_iters = it
                except ValueError:
                    pass

        return [
            {"type": "step", "stage": "summarize-title"},
            {"type": "parallel", "stages": ["literature-review", "explore"]},
            {"type": "step", "stage": "write-theory"},
            {
                "type": "loop",
                "name": "Refinement Loop",
                "base_stages": ["review-theory", "refine-theory"],
                "iterations": max_iters,
            },
        ]

    def run(self, task: Task, run_step: Callable) -> None:
        def get_step_output(stage_prefix: str):
            for s in task.steps:
                if (
                    s.stage.startswith(stage_prefix)
                    and s.status == StepStatus.COMPLETED
                ):
                    return s.outputs
            return None

        # Step 0: Summarize Title
        if not task.title:
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Generating summarized title...")
            title_data = run_step(
                task,
                "summarize-title",
                f"Please provide a very short, summarized title (maximum 5 words) for the following research phenomenon: {task.phenomenon}. "
                "Return a JSON object with the key 'title'.",
            )
            if title_data and isinstance(title_data, dict):
                task.title = title_data.get("title")

        # Step 1 & 2: Literature Review and Exploration in Parallel
        def get_lit_id():
            out = get_step_output("literature-review")
            return out.get("literature_review_id") if out else None

        lit_review_id = get_lit_id()
        exploration_data = get_step_output("explore")
        exploration_id = (
            exploration_data.get("exploration_id") if exploration_data else None
        )

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
                        f"Please run the literature-review skill for the following phenomenon: ```\n{task.phenomenon}\n```\n"
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
                        f"Please run the explore skill for the following phenomenon: ```\n{task.phenomenon}\n```\n"
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

            # Update IDs from results
            for res in results.values():
                if res and isinstance(res, dict):
                    if "literature_review_id" in res:
                        lit_review_id = res["literature_review_id"]
                    if "exploration_id" in res:
                        exploration_id = res["exploration_id"]

        if not lit_review_id or not exploration_id:
            raise Exception("Required research data (literature review or exploration) is missing.")

        # Step 3: Initial Theory
        theory_data = get_step_output("write-theory")
        theory_id = theory_data.get("theory_id") if theory_data else None
        if not theory_id:
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Developing initial theory...")
            theory_data = run_step(
                task,
                "write-theory",
                f"Please run the write-theory skill for the following phenomenon: ```\n{task.phenomenon}\n```\n"
                f"Use exploration_id: {exploration_id} and literature_review_id: {lit_review_id}. "
                "When you are done, return a JSON object with the key 'theory_id'.",
            )
            if theory_data:
                theory_id = theory_data.get("theory_id")
        if not theory_id:
            raise Exception("Theory generation failed to return a theory ID.")

        # Step 4: Iterative Review and Refinement
        i = 1
        while True:
            # Review
            review_data = get_step_output(f"review-theory-{i}")
            if not review_data:
                print(
                    f"[ORCHESTRATOR] [{task.id[:8]}][Iteration {i}] Reviewing theory..."
                )
                review_data = run_step(
                    task,
                    f"review-theory-{i}",
                    f"Please run the review-theory skill for the following theory_id: {theory_id}. "
                    "When you are done, return a JSON object with the key 'review_ids' (a list of strings).",
                )
            
            # If review_data is still None at this point, run_step should have raised
            if not review_data:
                raise Exception(f"Theory review for iteration {i} failed.")
            
            review_ids = review_data.get("review_ids", [])
            if not review_ids:
                # This is a legitimate end of the loop
                break

            # Refine
            refine_data = get_step_output(f"refine-theory-{i}")
            if not refine_data:
                print(
                    f"[ORCHESTRATOR] [{task.id[:8]}][Iteration {i}] Refining theory..."
                )
                refine_data = run_step(
                    task,
                    f"refine-theory-{i}",
                    f"Please run the refine-theory skill for the following theory_id: {theory_id}. "
                    f"Use literature_review_id: {lit_review_id}. "
                    "When you are done, return a JSON object with the keys 'theory_id' and 'major_changes' (boolean) to indicate if any major changes have been made to the theory.",
                )
            
            if not refine_data:
                raise Exception(f"Theory refinement for iteration {i} failed.")

            theory_id = refine_data.get("theory_id")
            if not theory_id:
                raise Exception(f"Theory refinement for iteration {i} failed to return a new theory ID.")

            i += 1
            if i > 3: # Safety cap
                break
