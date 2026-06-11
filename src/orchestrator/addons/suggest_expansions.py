from ..models import Addon, StepCategory
from .base import AddonHandler
from orchestrator.prompts import get_suggest_expansions_prompt

class SuggestExpansionsAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "suggest-expansions"

    @property
    def category(self) -> StepCategory:
        return StepCategory.REVIEW

    def get_prompt(self, addon: Addon) -> str:
        return get_suggest_expansions_prompt(addon.theory_id)
