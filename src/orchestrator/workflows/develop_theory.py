from typing import Any, Callable, List, Dict
from concurrent.futures import ThreadPoolExecutor
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
            if s.stage.startswith("review-theory-") or s.stage.startswith("refine-theory-"):
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
            }
        ]

    def run(self, task: Task, run_step: Callable) -> None:
        def get_step_output(stage_prefix: str):
            for s in task.steps:
                if s.stage.startswith(stage_prefix) and s.status == StepStatus.COMPLETED:
                    return s.outputs
            return None

        # Step 0: Summarize Title
        if not task.title:
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Generating summarized title...")
            title_data = run_step(
                task,
                "summarize-title",
                f"Please provide a very short, summarized title (maximum 5 words) for the following research phenomenon: {task.phenomenon}. "
                "Return a JSON object with the key 'title'."
            )
            if title_data and isinstance(title_data, dict):
                task.title = title_data.get("title")

        # Step 1 & 2: Literature Review and Exploration in Parallel
        def get_lit_id():
            out = get_step_output("literature-review")
            return out.get("literature_review_id") if out else None

        lit_review_id = get_lit_id()
        exploration_data = get_step_output("explore")
        exploration_id = exploration_data.get("exploration_id") if exploration_data else None

        if not lit_review_id or not exploration_id:
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Running Literature Review and Exploration in parallel...")
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = []
                if not lit_review_id:
                    futures.append(executor.submit(
                        run_step, task, "literature-review",
                        f"Please run the literature-review skill for the following phenomenon: {task.phenomenon}. "
                        "When you are done, return a JSON object with the key 'literature_review_id'."
                    ))
                if not exploration_id:
                    futures.append(executor.submit(
                        run_step, task, "explore",
                        f"Please run the explore skill for the following phenomenon: {task.phenomenon}. "
                        "When you are done, return a JSON object with the key 'exploration_id'."
                    ))
                
                results = [f.result() for f in futures]
                for res in results:
                    if res and isinstance(res, dict):
                        if "literature_review_id" in res:
                            lit_review_id = res["literature_review_id"]
                        if "exploration_id" in res:
                            exploration_id = res["exploration_id"]

        if not lit_review_id or not exploration_id: return

        # Step 3: Initial Theory
        theory_data = get_step_output("write-theory")
        theory_id = theory_data.get("theory_id") if theory_data else None
        if not theory_id:
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Developing initial theory...")
            theory_data = run_step(
                task,
                "write-theory",
                f"Please run the write-theory skill for the following phenomenon: {task.phenomenon}. "
                f"Use exploration_id: {exploration_id} and literature_review_id: {lit_review_id}. "
                "When you are done, return a JSON object with the key 'theory_id'."
            )
            if theory_data:
                theory_id = theory_data.get("theory_id")
        if not theory_id: return

        # Step 4: Iterative Review and Refinement
        i = 1
        while True:
            # Review
            review_data = get_step_output(f"review-theory-{i}")
            if not review_data:
                print(f"[ORCHESTRATOR] [{task.id[:8]}][Iteration {i}] Reviewing theory...")
                review_data = run_step(
                    task,
                    f"review-theory-{i}",
                    f"Please run the review-theory skill for the following theory_id: {theory_id}. "
                    "When you are done, return a JSON object with the key 'review_ids' (a list of strings)."
                )
            if not review_data: break
            
            review_ids = review_data.get("review_ids", [])
            if not review_ids:
                break

            # Refine
            refine_data = get_step_output(f"refine-theory-{i}")
            if not refine_data:
                print(f"[ORCHESTRATOR] [{task.id[:8]}][Iteration {i}] Refining theory...")
                refine_data = run_step(
                    task,
                    f"refine-theory-{i}",
                    f"Please run the refine-theory skill for the following theory_id: {theory_id}. "
                    f"Use literature_review_id: {lit_review_id}. "
                    "When you are done, return a JSON object with the keys 'theory_id' and 'major_changes' (boolean)."
                )
            if not refine_data: break
            
            theory_id = refine_data.get("theory_id")
            if not theory_id: break
            
            i += 1
