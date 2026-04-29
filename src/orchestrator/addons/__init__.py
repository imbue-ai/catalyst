from typing import Dict
from .base import AddonHandler
from .streamline_theory import StreamlineTheoryAddon
from .review_theory import ReviewTheoryAddon
from .refine_theory import RefineTheoryAddon
from .refinement_loop import RefinementLoopAddon
from .evolve_loop import EvolveLoopAddon

_ADDONS: Dict[str, AddonHandler] = {
    "streamline-theory": StreamlineTheoryAddon(),
    "review-theory": ReviewTheoryAddon(),
    "refine-theory": RefineTheoryAddon(),
    "refinement-loop": RefinementLoopAddon(),
    "evolve-loop": EvolveLoopAddon(),
}

def get_addon_handler(name: str) -> AddonHandler:
    return _ADDONS.get(name)