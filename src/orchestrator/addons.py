from abc import ABC, abstractmethod
from typing import Dict, Any, Callable
from .models import Addon, Task, StepStatus
from .state import get_task_lock

class AddonHandler(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def get_structure(self, addon: Addon, index: int, task: Task) -> Dict[str, Any]:
        return {"type": "step", "stage": f"addon-{addon.type}-{index}"}

    def run(self, task: Task, run_step: Callable, addon: Addon, index: int) -> None:
        stage = f"addon-{addon.type}-{index}"
        
        # Check if already completed
        completed = False
        with get_task_lock(task.id):
            for s in task.steps:
                if s.stage == stage and s.status == StepStatus.COMPLETED:
                    completed = True
                    break
        
        if not completed:
            print(f"[ORCHESTRATOR] [{task.id[:8]}] Running addon {stage}...")
            prompt = self.get_prompt(addon)
            run_step(task, stage, prompt)

    def get_prompt(self, addon: Addon) -> str:
        raise NotImplementedError()

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

from .workflows.base import run_refinement_loop

class RefinementLoopAddon(AddonHandler):
    @property
    def name(self) -> str:
        return "refinement-loop"

    def get_structure(self, addon: Addon, index: int, task: Task) -> Dict[str, Any]:
        max_iters = addon.max_refinements if hasattr(addon, 'max_refinements') and addon.max_refinements is not None else 3
        return {
            "type": "loop",
            "name": "Refinement Loop",
            "base_stages": [f"addon-{index}-review-theory", f"addon-{index}-refine-theory"],
            "iterations": max_iters,
        }

    def run(self, task: Task, run_step: Callable, addon: Addon, index: int) -> None:
        max_refinements = addon.max_refinements if hasattr(addon, 'max_refinements') and addon.max_refinements is not None else 3
        apply_extensions = addon.apply_extensions if hasattr(addon, 'apply_extensions') and addon.apply_extensions is not None else False
        
        run_refinement_loop(
            task=task,
            run_step_fn=run_step,
            theory_id=addon.theory_id,
            lit_review_id=None,
            apply_extensions=apply_extensions,
            max_refinements=max_refinements,
            stage_prefix=f"addon-{index}-"
        )

    def get_prompt(self, addon: Addon) -> str:
        pass

_ADDONS: Dict[str, AddonHandler] = {
    "streamline-theory": StreamlineTheoryAddon(),
    "review-theory": ReviewTheoryAddon(),
    "refine-theory": RefineTheoryAddon(),
    "refinement-loop": RefinementLoopAddon(),
}

def get_addon_handler(name: str) -> AddonHandler:
    return _ADDONS.get(name)