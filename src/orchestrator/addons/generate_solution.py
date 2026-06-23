from ..models import Addon, StepCategory
from .base import AddonHandler
from orchestrator.prompts import get_propose_experiment_prompt


class GenerateSolutionAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "generate-solution"

    @property
    def category(self) -> StepCategory:
        return StepCategory.THEORY_WRITING

    def get_prompt(self, addon: Addon) -> str:
        if not addon.theory_id:
            raise ValueError("generate-solution addon requires theory_id")
        return get_propose_experiment_prompt(addon.theory_id, propose_solution="always")
