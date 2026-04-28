import os
import subprocess
from typing import Any, Callable, List, Dict
from ..models import Task, StepStatus
from .base import Workflow


class RefineTheoryIdeaWorkflow(Workflow):
    MAX_REFINEMENT_ITERATIONS = 3

    @property
    def name(self) -> str:
        return "refine-theory-idea"

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
            {"type": "step", "stage": "support-idea"},
            {
                "type": "loop",
                "name": "Refinement Loop",
                "base_stages": ["review-theory", "refine-theory"],
                "iterations": max_iters,
            },
        ]

    def run(self, task: Task, run_step: Callable) -> None:
        # Initialize DB folder
        if not os.path.exists(task.db_path):
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Initializing DB folder...")
            env = os.environ.copy()
            env["AI_SCIENTIST_DB_PATH"] = task.db_path
            subprocess.run(
                ["uv", "run", "python", "context_manager.py", "init"],
                env=env,
                check=True,
            )

        def get_step_output(stage_prefix: str):
            for s in task.steps:
                if (
                    s.stage.startswith(stage_prefix)
                    and s.status == StepStatus.COMPLETED
                ):
                    return s.outputs
            return None

        idea = task.workflow_inputs["idea"]
        apply_extensions = task.workflow_inputs.get("apply_extensions", False)

        # Step 0: Summarize Title
        if not task.title:
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Generating summarized title...")
            title_data = run_step(
                task,
                "summarize-title",
                f"Please provide a very short, summarized title (maximum 5 words) for the following research idea:\n```\n{idea}\n```\n"
                "Return a JSON object with the key 'title'.",
            )
            if title_data and isinstance(title_data, dict):
                task.title = title_data.get("title")

        # Step 1: Support Idea
        support_data = get_step_output("support-idea")
        theory_id = support_data.get("theory_id") if support_data else None

        if not theory_id:
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Running support idea...")
            support_data = run_step(
                task,
                "support-idea",
                f"Please run the support-idea skill for the following idea:\n```\n{idea}\n```\n"
                "When you are done, return a JSON object with the key 'theory_id'.",
            )
            if support_data:
                theory_id = support_data.get("theory_id")

        if not theory_id:
            raise Exception("support-idea failed to return a theory ID.")

        # Step 2: Iterative Review and Refinement
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

            if not review_data:
                raise Exception(f"Theory review for iteration {i} failed.")

            review_ids = review_data.get("review_ids", [])
            if not review_ids:
                break

            # Refine
            refine_data = get_step_output(f"refine-theory-{i}")
            if not refine_data:
                print(
                    f"[ORCHESTRATOR] [{task.id[:8]}][Iteration {i}] Refining theory..."
                )
                prompt = (
                    f"Please run the refine-theory skill for the following theory_id: {theory_id}. "
                    "When you are done, return a JSON object with the keys 'theory_id' and 'major_changes' (boolean) to indicate if any major changes have been made to the theory."
                )
                if not apply_extensions:
                    prompt += "\n\nCRITICAL: Do not apply extensions."

                refine_data = run_step(task, f"refine-theory-{i}", prompt)

            if not refine_data:
                raise Exception(f"Theory refinement for iteration {i} failed.")

            theory_id = refine_data.get("theory_id")
            if not theory_id:
                raise Exception(
                    f"Theory refinement for iteration {i} failed to return a new theory ID."
                )
            if not refine_data.get("major_changes", True):
                break

            i += 1
            if i > self.MAX_REFINEMENT_ITERATIONS:
                break
