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
        Runs the agent and returns (json_output, session_id, error).

        `session_id` is the identifier used by the dashboard's "Inspect
        Agent" panel. The direct `claude` / `gemini` runners write the CLI
        session UUID here (the direct `agy` runner has none); the
        `mngr-claude`/`mngr-antigravity` runners write the mngr agent name
        (e.g. "cata-abcd1234-..."). The frontend picks the right `Inspect
        Agent` command from the framework type.

        `stage` is the workflow stage name (e.g. "write-theory"). The
        mngr runners use it to label and name their agents; the direct
        runners ignore it.
        """
        pass
