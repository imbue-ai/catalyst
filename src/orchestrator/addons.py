from abc import ABC, abstractmethod
from typing import Dict, Type
from .models import Addon

class AddonHandler(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def get_prompt(self, addon: Addon) -> str:
        pass

class StreamlineTheoryAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "streamline-theory"

    def get_prompt(self, addon: Addon) -> str:
        prompt = f"Please run the streamline-theory skill for the following theory_id: {addon.theory_id}."
        if addon.direction:
            prompt += f" Direction: {addon.direction}"
        prompt += "\nWhen you are done, return a JSON object with the key 'theory_id'."
        return prompt

class ReviewTheoryAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "review-theory"

    def get_prompt(self, addon: Addon) -> str:
        return f"Please run the review-theory skill for the following theory_id: {addon.theory_id}.\nWhen you are done, return a JSON object with the key 'review_ids' (a list of strings)."

class RefineTheoryAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "refine-theory"

    def get_prompt(self, addon: Addon) -> str:
        return f"Please run the refine-theory skill for the following theory_id: {addon.theory_id}.\nWhen you are done, return a JSON object with the key 'theory_id'."

_ADDONS: Dict[str, AddonHandler] = {
    "streamline-theory": StreamlineTheoryAddon(),
    "review-theory": ReviewTheoryAddon(),
    "refine-theory": RefineTheoryAddon(),
}

def get_addon_handler(name: str) -> AddonHandler:
    return _ADDONS.get(name)