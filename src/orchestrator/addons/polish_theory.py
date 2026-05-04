from ..models import Addon
from .base import AddonHandler
from orchestrator.prompts import get_polish_theory_prompt

class PolishTheoryAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "polish-theory"

    def get_prompt(self, addon: Addon) -> str:
        return get_polish_theory_prompt(addon.theory_id)
