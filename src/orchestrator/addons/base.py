from abc import ABC, abstractmethod
import logging
from typing import Dict, Any, Callable
from ..models import Addon, Task, StepStatus, StepCategory
from ..state import get_task_lock

logger = logging.getLogger(__name__)


class AddonHandler(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def category(self) -> StepCategory:
        pass

    @property
    def cost(self) -> int:
        return 1

    def get_structure(self, addon: Addon, index: int, task: Task) -> Dict[str, Any]:
        return {"type": "step", "stage": f"addon-{addon.type}-{index}"}

    def run(self, task: Task, run_step: Callable, addon: Addon, index: int) -> None:
        stage = f"addon-{addon.type}-{index}"

        # Check if already completed or canceled
        completed_or_canceled = False
        with get_task_lock(task.id):
            for s in task.steps:
                if s.stage == stage and s.status in (
                    StepStatus.COMPLETED,
                    StepStatus.CANCELED,
                ):
                    completed_or_canceled = True
                    break

        if not completed_or_canceled:
            logger.debug(f"[ORCHESTRATOR] [{task.id[:8]}] Running addon {stage}...")
            prompt = self.get_prompt(addon)
            run_step(task, stage, prompt, cost=self.cost, category=self.category)

    def get_prompt(self, addon: Addon) -> str:
        raise NotImplementedError()
