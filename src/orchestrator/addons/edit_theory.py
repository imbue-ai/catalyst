from ..models import Addon
from .base import AddonHandler
from orchestrator.prompts import get_edit_theory_prompt

class EditTheoryAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "edit-theory"

    def get_prompt(self, addon: Addon) -> str:
        return get_edit_theory_prompt(addon.theory_id, addon.instruction or "", lit_review_id=addon.lit_review_id)
