from abc import ABC, abstractmethod
from typing import Dict, Any, Callable
from ..models import Addon, Task, StepStatus
from ..state import get_task_lock

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