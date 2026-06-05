from typing import Optional
from .base import AgentRunner
from .gemini import GeminiAgentRunner
from .claude import ClaudeAgentRunner
from .codex import CodexAgentRunner
from .agy import AgyAgentRunner
from .mngr_claude import MngrClaudeAgentRunner
from .mngr_antigravity import MngrAntigravityAgentRunner


def get_agent_runner(framework: str) -> Optional[AgentRunner]:
    if framework == "gemini":
        return GeminiAgentRunner()
    if framework == "claude":
        return ClaudeAgentRunner()
    if framework == "codex":
        return CodexAgentRunner()
    if framework == "agy":
        return AgyAgentRunner()
    if framework == "mngr-claude":
        return MngrClaudeAgentRunner()
    if framework == "mngr-antigravity":
        return MngrAntigravityAgentRunner()
    return None
