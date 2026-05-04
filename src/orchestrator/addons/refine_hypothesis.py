from ..models import Addon
from .base import AddonHandler
from orchestrator.prompts import get_refine_hypothesis_prompt

class RefineHypothesisAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "refine-hypothesis"

    def get_prompt(self, addon: Addon) -> str:
        return get_refine_hypothesis_prompt(addon.theory_id, addon.review_id)
