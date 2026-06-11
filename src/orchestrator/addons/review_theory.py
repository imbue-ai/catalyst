from ..models import Addon, StepCategory
from .base import AddonHandler
from orchestrator.prompts import get_review_theory_prompt


class ReviewTheoryAddon(AddonHandler):
    @property
    def cost(self) -> int:
        return 3

    @property
    def name(self) -> str:
        return "review-theory"

    @property
    def category(self) -> StepCategory:
        return StepCategory.REVIEW

    def get_prompt(self, addon: Addon) -> str:
        return get_review_theory_prompt(addon.theory_id)
