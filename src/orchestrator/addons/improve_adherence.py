from ..models import Addon, StepCategory
from .base import AddonHandler
from orchestrator.prompts import get_improve_adherence_prompt

class ImproveAdherenceAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "improve-adherence"

    @property
    def category(self) -> StepCategory:
        return StepCategory.THEORY_WRITING

    def get_prompt(self, addon: Addon) -> str:
        return get_improve_adherence_prompt(addon.theory_id, addon.review_id, lit_review_id=addon.lit_review_id)
