from typing import Dict
from .base import AddonHandler
from .streamline_theory import StreamlineTheoryAddon
from .review_theory import ReviewTheoryAddon
from .refine_theory import RefineTheoryAddon
from .refinement_loop import RefinementLoopAddon
from .evolve_loop import EvolveLoopAddon
from .polish_theory import PolishTheoryAddon
from .refine_hypothesis import RefineHypothesisAddon
from .falsify_hypothesis import FalsifyHypothesisAddon
from .suggest_expansions import SuggestExpansionsAddon
from .expand_theory import ExpandTheoryAddon
from .streamline_theory_variations import StreamlineTheoryVariationsAddon
from .edit_theory import EditTheoryAddon
from .score_theories import ScoreTheoriesAddon
from .write_different_theory import WriteDifferentTheoryAddon

_ADDONS: Dict[str, AddonHandler] = {
    "streamline-theory": StreamlineTheoryAddon(),
    "review-theory": ReviewTheoryAddon(),
    "refine-theory": RefineTheoryAddon(),
    "refinement-loop": RefinementLoopAddon(),
    "evolve-loop": EvolveLoopAddon(),
    "polish-theory": PolishTheoryAddon(),
    "refine-hypothesis": RefineHypothesisAddon(),
    "falsify-hypothesis": FalsifyHypothesisAddon(),
    "suggest-expansions": SuggestExpansionsAddon(),
    "expand-theory": ExpandTheoryAddon(),
    "streamline-theory-variations": StreamlineTheoryVariationsAddon(),
    "edit-theory": EditTheoryAddon(),
    "score-theories": ScoreTheoriesAddon(),
    "write-different-theory": WriteDifferentTheoryAddon(),
}

def get_addon_handler(name: str) -> AddonHandler:
    return _ADDONS.get(name)