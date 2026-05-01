from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, Callable

class AgentRunner(ABC):
    @abstractmethod
    def run(
        self,
        task_id: str,
        prompt: str,
        env_folder: str,
        model: Optional[str] = None,
        tx_id: Optional[str] = None,
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Runs the agent and returns (json_output, session_id, error).
        """
        pass
