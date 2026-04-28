from ..models import Addon
from .base import AddonHandler

class ReviewTheoryAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "review-theory"

    def get_prompt(self, addon: Addon) -> str:
        return f"Please run the review-theory skill for the following theory_id: {addon.theory_id}.\nWhen you are done, return a JSON object with the key 'review_ids' (a list of strings)."