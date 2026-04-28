from ..models import Addon
from .base import AddonHandler

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