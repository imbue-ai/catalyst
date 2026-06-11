from ..models import Addon, StepCategory
from .base import AddonHandler
from orchestrator.prompts import get_refine_theory_prompt

class RefineTheoryAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "refine-theory"

    @property
    def category(self) -> StepCategory:
        return StepCategory.THEORY_WRITING

    def get_prompt(self, addon: Addon) -> str:
        return get_refine_theory_prompt(
            addon.theory_id,
            apply_expansions=addon.apply_expansions,
            lit_review_id=addon.lit_review_id,
        )
