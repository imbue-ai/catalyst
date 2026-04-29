from typing import Any, Callable, List, Dict
from ..models import Task
from .base import Workflow, run_step_if_needed


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
        if not task.title:
            title_data = run_step_if_needed(
                task,
                run_step,
                "summarize-title",
                f"Please read the following file and provide a very short, summarized title (maximum 5 words) for the theory it contains: {file_path}. "
                "Return a JSON object with the key 'title'.",
            )
            if title_data and isinstance(title_data, dict):
                task.title = title_data.get("title")

        # Step 1: Import Theory
        import_data = run_step_if_needed(
            task,
            run_step,
            "import-theory",
            f"Please run the import-theory skill for the following file path: {file_path}. "
            "When you are done, return ONLY a JSON object with the key 'theory_id'.",
        )
        theory_id = import_data.get("theory_id") if import_data else None
        if not theory_id and not (import_data and import_data.get("_canceled")):
            raise Exception("import-theory failed to return a theory ID.")
