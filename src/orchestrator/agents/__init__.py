from typing import Optional
from .base import AgentRunner
from .claude import ClaudeAgentRunner
from .mngr_antigravity import MngrAntigravityAgentRunner
from .mngr_claude import MngrClaudeAgentRunner


def get_agent_runner(framework: str) -> Optional[AgentRunner]:
    if framework == "claude":
        return ClaudeAgentRunner()
    if framework == "mngr-claude":
        return MngrClaudeAgentRunner()
    if framework == "mngr-antigravity":
        return MngrAntigravityAgentRunner()
    return None
