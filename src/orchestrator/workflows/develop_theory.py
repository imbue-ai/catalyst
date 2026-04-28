import threading
from typing import Any, Callable, List, Dict
from ..models import Task
from .base import Workflow, get_step_output, run_step_if_needed, run_refinement_loop


class DevelopTheoryWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "develop-theory"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        max_refinements = int(task.workflow_inputs.get("max_refinements", 3))
        # Count iterations dynamically based on steps
        max_iters = max_refinements if max_refinements > 0 else 0
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

        structure = [
            {"type": "step", "stage": "summarize-title"},
            {"type": "parallel", "stages": ["literature-review", "explore"]},
            {"type": "step", "stage": "write-theory"},
        ]
        
        if max_iters > 0:
            structure.append({
                "type": "loop",
                "name": "Refinement Loop",
                "base_stages": ["review-theory", "refine-theory"],
                "iterations": max_iters,
            })
            
        return structure

    def run(self, task: Task, run_step: Callable) -> None:
        self.init_db(task)

        # Step 0: Summarize Title
        if not task.title:
            title_data = run_step_if_needed(
                task, run_step, "summarize-title",
                f"Please provide a very short, summarized title (maximum 5 words) for the following research phenomenon: {task.workflow_inputs.get('phenomenon')}. "
                "Return a JSON object with the key 'title'."
            )
            if title_data and isinstance(title_data, dict):
                task.title = title_data.get("title")

        # Step 1 & 2: Literature Review and Exploration in Parallel
        lit_out = get_step_output(task, "literature-review")
        lit_review_id = lit_out.get("literature_review_id") if lit_out else None
        
        exp_out = get_step_output(task, "explore")
        exploration_id = exp_out.get("exploration_id") if exp_out else None

        if not lit_review_id or not exploration_id:
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Running Literature Review and Exploration in parallel...")

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

            # Update IDs from results
            for res in results.values():
                if res and isinstance(res, dict):
                    if "literature_review_id" in res:
                        lit_review_id = res["literature_review_id"]
                    elif "_canceled" in res:
                        pass # Allowed to be missing if canceled
                    
                    if "exploration_id" in res:
                        exploration_id = res["exploration_id"]
                    elif "_canceled" in res:
                        pass

        # We allow them to be None if the respective steps were canceled.
        # But if they failed without canceling, the loop above would have raised the error.

        # Step 3: Initial Theory
        theory_data = run_step_if_needed(
            task, run_step, "write-theory",
            f"Please run the write-theory skill for the following phenomenon:\n```\n{task.workflow_inputs.get('phenomenon')}\n```\n"
            f"Use exploration_id: {exploration_id} and literature_review_id: {lit_review_id}. "
            "When you are done, return a JSON object with the key 'theory_id'."
        )
        theory_id = theory_data.get("theory_id") if theory_data else None
        if not theory_id and not (theory_data and theory_data.get("_canceled")):
            raise Exception("Theory generation failed to return a theory ID.")

        if theory_id:
            # Step 4: Iterative Review and Refinement
            max_refinements = int(task.workflow_inputs.get("max_refinements", 3))
            run_refinement_loop(
                task, run_step, theory_id, lit_review_id, 
                apply_extensions=True, max_refinements=max_refinements
            )