from ..models import Addon, StepCategory
from .base import AddonHandler
from orchestrator.prompts import get_streamline_theory_variations_prompt

class StreamlineTheoryVariationsAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "streamline-theory-variations"

    @property
    def category(self) -> StepCategory:
        return StepCategory.THEORY_WRITING

    def get_prompt(self, addon: Addon) -> str:
        return get_streamline_theory_variations_prompt(addon.theory_id)
