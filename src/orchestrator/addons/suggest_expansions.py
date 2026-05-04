from ..models import Addon
from .base import AddonHandler
from orchestrator.prompts import get_suggest_expansions_prompt

class SuggestExpansionsAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "suggest-expansions"

    def get_prompt(self, addon: Addon) -> str:
        return get_suggest_expansions_prompt(addon.theory_id)
