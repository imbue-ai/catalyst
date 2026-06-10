from ..models import Addon
from .base import AddonHandler
from orchestrator.prompts import get_summarize_research_prompt

class SummarizeResearchAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "summarize-research"

    def get_prompt(self, addon: Addon) -> str:
        return get_summarize_research_prompt()
