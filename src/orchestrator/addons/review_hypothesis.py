from ..models import Addon
from .base import AddonHandler
from orchestrator.prompts import get_review_hypothesis_prompt

class ReviewHypothesisAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "review-hypothesis"

    def get_prompt(self, addon: Addon) -> str:
        return get_review_hypothesis_prompt(addon.theory_id, addon.hypothesis_title)
