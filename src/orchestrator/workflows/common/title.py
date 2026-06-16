from typing import Callable
from ...models import Task, StepCategory
from ..base import run_step_if_needed
from orchestrator.prompts import get_summarize_title_prompt

def run_summarize_title(task: Task, run_step_fn: Callable, content_desc: str) -> None:
    if not task.title:
        title_data = run_step_if_needed(
            task,
            run_step_fn,
            "summarize-title",
            get_summarize_title_prompt(content_desc),
            StepCategory.MISC,
        )
        if title_data and isinstance(title_data, dict):
            task.title = title_data.get("title")
