from typing import Optional
from .base import AgentRunner
from .claude import ClaudeAgentRunner
from .gemini import GeminiAgentRunner
from .mngr_claude import MngrClaudeAgentRunner
from .mngr_gemini import MngrGeminiAgentRunner


def get_agent_runner(framework: str) -> Optional[AgentRunner]:
    if framework == "claude":
        return ClaudeAgentRunner()
    if framework == "gemini":
        return GeminiAgentRunner()
    if framework == "mngr-claude":
        return MngrClaudeAgentRunner()
    if framework == "mngr-gemini":
        return MngrGeminiAgentRunner()
    return None
