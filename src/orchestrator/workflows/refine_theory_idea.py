from typing import Any, Callable, List, Dict
from ..models import Task
from .base import Workflow, run_step_if_needed

class RefineTheoryIdeaWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "refine-theory-idea"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        structure = [
            {"type": "step", "stage": "summarize-title"},
            {"type": "step", "stage": "support-idea"},
        ]
        if any(s.stage == "review-theory" for s in task.steps):
            structure.append({"type": "step", "stage": "review-theory"})
        if any(s.stage == "score-theories" for s in task.steps):
            structure.append({"type": "step", "stage": "score-theories"})
        return structure

    def run(self, task: Task, run_step: Callable) -> None:
        self.init_db(task)
        semaphore = threading.Semaphore(3)

        def bounded_run_step(task, stage, prompt):
            with semaphore:
                return run_step(task, stage, prompt)

        idea = task.workflow_inputs.get("idea", "")

        # Step 0: Summarize Title
        if not task.title:
            title_data = run_step_if_needed(
                task, bounded_run_step, "summarize-title",
                f"Please provide a very short, summarized title (maximum 5 words) for the following research idea: {idea}. "
                "Return a JSON object with the key 'title'."
            )
            if title_data and isinstance(title_data, dict):
                task.title = title_data.get("title")

        # Step 1: Support Idea
        support_data = run_step_if_needed(
            task, run_step, "support-idea",
            f"Please run the support-idea skill for the following idea:\n```\n{idea}\n```\n"
            "When you are done, return a JSON object with the key 'theory_id'."
        )
        theory_id = support_data.get("theory_id") if support_data else None
        if not theory_id and not (support_data and support_data.get("_canceled")):
            raise Exception("support-idea failed to return a theory ID.")

        if theory_id:
            # Step 2: Review Theory
            review_data = run_step_if_needed(
                task, run_step, "review-theory",
                f"Please run the review-theory skill for theory_id: {theory_id}. "
                "When you are done, return a JSON object with the key 'review_id'."
            )
            
            # Step 3: Score Theories
            score_data = run_step_if_needed(
                task, run_step, "score-theories",
                f"Please run the score-theories skill for the following theory_id: {theory_id}. "
                "When you are done, return a JSON object mapping each theory ID to its assigned score."
            )
            
            # TODO: Add new Refinement Loop here
