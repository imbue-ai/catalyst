import threading
import logging
from typing import Callable, Tuple, Optional
from ...models import Task
from ..base import get_step_output

logger = logging.getLogger(__name__)


def run_literature_review_and_exploration_parallel(
    task: Task, run_step_fn: Callable, phenomenon: str
) -> Tuple[Optional[str], Optional[str]]:
    lit_out = get_step_output(task, "literature-review")
    lit_review_id = lit_out.get("literature_review_id") if lit_out else None

    exp_out = get_step_output(task, "explore")
    exploration_id = exp_out.get("exploration_id") if exp_out else None

    if not lit_review_id or not exploration_id:
        logger.debug(
            f"[ORCHESTRATOR] [{task.id[:8]}] Running Literature Review and Exploration in parallel..."
        )

        results = {}
        errors = []

        def run_and_store(stage, prompt, key):
            try:
                results[key] = run_step_fn(task, stage, prompt)
            except Exception as e:
                errors.append(e)

        threads = []
        if not lit_review_id:
            t = threading.Thread(
                target=run_and_store,
                args=(
                    "literature-review",
                    f"Please run the literature-review skill for the following phenomenon:\n```\n{phenomenon}\n```\n"
                    "When you are done, return ONLY a JSON object with the key 'literature_review_id'.",
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
                    f"Please run the explore skill for the following phenomenon:\n```\n{phenomenon}\n```\n"
                    "When you are done, return ONLY a JSON object with the key 'exploration_id'.",
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
                if "literature_review_id" in res and isinstance(
                    res["literature_review_id"], str
                ):
                    lit_review_id = res["literature_review_id"]
                if "exploration_id" in res and isinstance(
                    res["exploration_id"], str
                ):
                    exploration_id = res["exploration_id"]

    return lit_review_id, exploration_id
