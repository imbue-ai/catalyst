from ..models import Addon, StepCategory
from .base import AddonHandler
from orchestrator.prompts import get_streamline_theory_prompt

class StreamlineTheoryAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "streamline-theory"

    @property
    def category(self) -> StepCategory:
        return StepCategory.THEORY_WRITING

    def get_prompt(self, addon: Addon) -> str:
        return get_streamline_theory_prompt(addon.theory_id, getattr(addon, 'direction', None))
