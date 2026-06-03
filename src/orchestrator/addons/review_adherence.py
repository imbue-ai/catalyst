from ..models import Addon
from .base import AddonHandler
from orchestrator.prompts import get_review_adherence_prompt

class ReviewAdherenceAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "review-adherence"

    def get_prompt(self, addon: Addon) -> str:
        return get_review_adherence_prompt(addon.theory_id)
