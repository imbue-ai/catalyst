from typing import Optional
from .base import AgentRunner
from .gemini import GeminiAgentRunner
from .claude import ClaudeAgentRunner
from .agy import AgyAgentRunner

def get_agent_runner(framework: str) -> Optional[AgentRunner]:
    if framework == "gemini":
        return GeminiAgentRunner()
    if framework == "claude":
        return ClaudeAgentRunner()
    if framework == "agy":
        return AgyAgentRunner()
    return None

