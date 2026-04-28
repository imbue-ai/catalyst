from abc import ABC, abstractmethod
from typing import Any, Callable, List, Dict

class Workflow(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def get_structure(self, task) -> List[Dict[str, Any]]:
        """Returns the structural representation of the workflow for the UI."""
        pass

    @abstractmethod
    def run(self, task, run_step_fn: Callable) -> None:
        """Executes the workflow."""
        pass
