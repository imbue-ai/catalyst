from ..models import Addon, StepCategory
from .base import AddonHandler
from orchestrator.prompts import get_review_adherence_prompt

class ReviewAdherenceAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "review-adherence"

    @property
    def category(self) -> StepCategory:
        return StepCategory.REVIEW

    def get_prompt(self, addon: Addon) -> str:
        return get_review_adherence_prompt(addon.theory_id)
