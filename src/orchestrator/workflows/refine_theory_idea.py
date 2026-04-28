from typing import Any, Callable, List, Dict
from ..models import Task
from .base import Workflow

class RefineTheoryIdeaWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "refine-theory-idea"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        max_refinements = int(task.workflow_inputs.get("max_refinements", 3))
        # Count iterations dynamically based on steps
        max_iters = max_refinements if max_refinements > 0 else 0
        for s in task.steps:
            if s.stage.startswith("review-theory-") or s.stage.startswith("refine-theory-"):
                try:
                    it = int(s.stage.split("-")[-1])
                    if it > max_iters:
                        max_iters = it
                except ValueError:
                    pass

        structure = [
            {"type": "step", "stage": "summarize-title"},
            {"type": "step", "stage": "support-idea"},
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

        idea = task.workflow_inputs.get("idea", "")
        apply_extensions = task.workflow_inputs.get("apply_extensions", False)

        # Step 0: Summarize Title
        if not task.title:
            title_data = self.run_step_if_needed(
                task, run_step, "summarize-title",
                f"Please provide a very short, summarized title (maximum 5 words) for the following research idea: {idea}. "
                "Return a JSON object with the key 'title'."
            )
            if title_data and isinstance(title_data, dict):
                task.title = title_data.get("title")

        # Step 1: Support Idea
        support_data = self.run_step_if_needed(
            task, run_step, "support-idea",
            f"Please run the support-idea skill for the following idea:\n```\n{idea}\n```\n"
            "When you are done, return a JSON object with the key 'theory_id'."
        )
        theory_id = support_data.get("theory_id") if support_data else None
        if not theory_id:
            raise Exception("support-idea failed to return a theory ID.")

        # Step 2: Iterative Review and Refinement
        max_refinements = int(task.workflow_inputs.get("max_refinements", 3))
        i = 1
        while i <= max_refinements:
            # Review
            review_data = self.run_step_if_needed(
                task, run_step, f"review-theory-{i}",
                f"Please run the review-theory skill for the following theory_id: {theory_id}. "
                "When you are done, return a JSON object with the key 'review_ids' (a list of strings)."
            )

            if not review_data:
                raise Exception(f"Theory review for iteration {i} failed.")

            review_ids = review_data.get("review_ids", [])
            if not review_ids:
                break

            # Refine
            prompt = (
                f"Please run the refine-theory skill for the following theory_id: {theory_id}. "
                "When you are done, return a JSON object with the keys 'theory_id' and 'major_changes' (boolean) to indicate if any major changes have been made to the theory."
            )
            if not apply_extensions:
                prompt += "\n\nCRITICAL: Do not apply extensions."
                
            refine_data = self.run_step_if_needed(
                task, run_step, f"refine-theory-{i}", prompt
            )

            if not refine_data:
                raise Exception(f"Theory refinement for iteration {i} failed.")

            theory_id = refine_data.get("theory_id")
            if not theory_id:
                raise Exception(f"Theory refinement for iteration {i} failed to return a new theory ID.")
            if not refine_data.get("major_changes", True):
                break

            i += 1