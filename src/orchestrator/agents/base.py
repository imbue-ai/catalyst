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
        stage: Optional[str] = None,
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Runs the agent and returns (json_output, agent_name, error).

        agent_name is the mngr agent identifier (a stable name we control)
        used by the dashboard so a user can `mngr connect <agent_name>` to
        attach to the live tmux session, or `mngr transcript <agent_name>`
        post-mortem.
        """
        pass
