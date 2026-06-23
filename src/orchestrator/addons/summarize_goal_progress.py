from ..models import Addon, StepCategory
from .base import AddonHandler
from orchestrator.prompts import get_summarize_goal_progress_prompt

class SummarizeGoalProgressAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "summarize-goal-progress"

    @property
    def category(self) -> StepCategory:
        return StepCategory.MISC

    def get_prompt(self, addon: Addon) -> str:
        return get_summarize_goal_progress_prompt()
