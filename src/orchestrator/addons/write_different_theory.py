from ..models import Addon
from .base import AddonHandler
from orchestrator.prompts import get_write_different_theory_prompt


class WriteDifferentTheoryAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "write-different-theory"

    def get_prompt(self, addon: Addon) -> str:
        if not addon.theory_ids:
            raise ValueError("write-different-theory addon requires theory_ids")
        return get_write_different_theory_prompt(addon.theory_ids, lit_review_id=addon.lit_review_id)
