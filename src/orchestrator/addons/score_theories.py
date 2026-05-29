from ..models import Addon
from .base import AddonHandler
from orchestrator.prompts import get_score_theories_prompt


class ScoreTheoriesAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "score-theories"

    def get_prompt(self, addon: Addon) -> str:
        if not addon.theory_ids:
            raise ValueError("score-theories addon requires theory_ids")
        return get_score_theories_prompt(addon.theory_ids)
