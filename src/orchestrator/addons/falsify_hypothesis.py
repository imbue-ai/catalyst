from ..models import Addon, StepCategory
from .base import AddonHandler
from orchestrator.prompts import get_falsify_hypothesis_prompt


class FalsifyHypothesisAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "falsify-hypothesis"

    @property
    def category(self) -> StepCategory:
        return StepCategory.REVIEW

    def get_prompt(self, addon: Addon) -> str:
        return get_falsify_hypothesis_prompt(addon.theory_id, addon.hypothesis_title)
