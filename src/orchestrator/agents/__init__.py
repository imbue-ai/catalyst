from typing import Optional
from .base import AgentRunner
from .gemini import GeminiAgentRunner
from .claude import ClaudeAgentRunner

def get_agent_runner(framework: str) -> Optional[AgentRunner]:
    if framework == "gemini":
        return GeminiAgentRunner()
    if framework == "claude":
        return ClaudeAgentRunner()
    return None
