import logging
import os
import re
import tempfile
from typing import Any, Dict, List, Optional

from ...models import Task
from ...utils import run_context_manager
from ..base import run_local_step_if_needed

logger = logging.getLogger(__name__)


def run_initialize_theories(task: Task) -> Optional[List[str]]:
    """Initializes starter theories for each strand of the workflow.

    Runs as a local step and returns a list of theory IDs, or None if canceled.
    """
    goal = task.workflow_inputs.get("goal")
    assert goal, "Goal is required."
    num_strands = int(task.workflow_inputs.get("num_strands", 3))

    def _initialize_theories() -> Dict[str, Any]:
        abs_env_folder = os.path.abspath(task.env_folder)
        tmp_dir = os.path.join(abs_env_folder, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)

        theory_ids = []
        for idx in range(num_strands):
            # Create unique output folder under tmp
            output_dir = tempfile.mkdtemp(
                prefix=f"initialize-theories-output-strand-{idx + 1}-",
                dir=tmp_dir,
            )

            # Create theory.md
            theory_file = os.path.join(output_dir, "theory.md")
            with open(theory_file, "w", encoding="utf-8") as f:
                f.write(
                    "# Starter Theory\n**Research goal:** "
                    + goal.strip()
                    + "\n\nThis is a placeholder theory. No research has been conducted yet.\n"
                )

            # Store results using run_context_manager in a subprocess
            out = run_context_manager(
                task,
                [
                    "store_results",
                    "--from_agent_type",
                    "initialize-theories",
                    "--from_folder",
                    output_dir,
                ],
            )

            # Extract theory ID from output
            match = re.search(r"Result stored with ID: (\S+)", out)
            if not match:
                raise Exception(f"Failed to parse stored results ID. Output: {out}")
            theory_ids.append(match.group(1))

        return {"theory_ids": theory_ids}

    init_data = run_local_step_if_needed(
        task,
        "initialize-theories",
        _initialize_theories,
    )

    theory_ids = []
    if init_data:
        theory_ids = init_data.get("theory_ids") or []

    if not theory_ids:
        if init_data and init_data.get("_canceled"):
            return None
        raise Exception("Initialization failed to return theory IDs.")

    return theory_ids
