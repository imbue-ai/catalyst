from ..models import Addon
from .base import AddonHandler


class RefineTheoryAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "refine-theory"

    def get_prompt(self, addon: Addon) -> str:
        return f"Please run the refine-theory skill for the following theory_id: {addon.theory_id}.\nWhen you are done, return ONLY a JSON object with the key 'theory_id'."
