from typing import Any, Callable, List, Dict
from ..models import Task
from .base import Workflow, run_step_if_needed
from .common import run_summarize_title
from orchestrator.prompts import get_import_theory_prompt

class ImportTheoryWorkflow(Workflow):
    @property
    def name(self) -> str:
        return "import-theory"

    def get_structure(self, task: Task) -> List[Dict[str, Any]]:
        return [
            {"type": "step", "stage": "summarize-title"},
            {"type": "step", "stage": "import-theory"},
        ]

    def run(self, task: Task, run_step: Callable) -> None:
        self.init_db(task)

        file_path = task.workflow_inputs.get("file_path", "")

        # Step 0: Summarize Title
        run_summarize_title(task, run_step, f"theory file: {file_path}")

        # Step 1: Import Theory
        import_data = run_step_if_needed(
            task,
            run_step,
            "import-theory",
            get_import_theory_prompt(file_path),
        )
        theory_id = import_data.get("theory_id") if import_data else None
        if not theory_id and not (import_data and import_data.get("_canceled")):
            raise Exception("import-theory failed to return a theory ID.")
