from typing import Optional
from .base import AgentRunner
from .gemini import GeminiAgentRunner
from .claude import ClaudeAgentRunner
from .codex import CodexAgentRunner
from .agy import AgyAgentRunner
from .mngr_claude import MngrClaudeAgentRunner
from .mngr_antigravity import MngrAntigravityAgentRunner


def get_agent_runner(framework: str, disable_sandboxing: bool = False) -> Optional[AgentRunner]:
    if framework == "gemini":
        return GeminiAgentRunner(disable_sandboxing=disable_sandboxing)
    if framework == "claude":
        return ClaudeAgentRunner(disable_sandboxing=disable_sandboxing)
    if framework == "codex":
        return CodexAgentRunner(disable_sandboxing=disable_sandboxing)
    if framework == "agy":
        return AgyAgentRunner(disable_sandboxing=disable_sandboxing)
    if framework == "mngr-claude":
        return MngrClaudeAgentRunner(disable_sandboxing=disable_sandboxing)
    if framework == "mngr-antigravity":
        return MngrAntigravityAgentRunner(disable_sandboxing=disable_sandboxing)
    return None
