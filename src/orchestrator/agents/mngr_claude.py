from typing import Any, Dict, List, Optional

from .mngr_runner import MngrAgentRunner

# `--dangerously-skip-permissions` and `--verbose` live in
# `.mngr/settings.toml` (`agent_types.claude.cli_args`) so they apply to
# every claude invocation. The friction-log instruction that used to be
# `_ADDITIONAL_SYSTEM_PROMPT` is now in `BASE_CLAUDE_MD` (see
# `create_environment.py`), which gets auto-loaded by Claude from the
# work_dir's `CLAUDE.md`.


def _build_agent_args(model: Optional[str]) -> List[str]:
    if model:
        return ["--model", model]
    return []


def _extract_assistant_text(event: Dict[str, Any]) -> Optional[str]:
    if event.get("type") != "assistant_message":
        return None
    text = event.get("text")
    if isinstance(text, str) and text:
        return text
    return None


def _extract_status(event: Dict[str, Any]) -> Optional[str]:
    if event.get("type") == "assistant_message":
        text = event.get("text")
        if isinstance(text, str) and text.strip():
            return " ".join(text.split())
    return None


class MngrClaudeAgentRunner(MngrAgentRunner):
    def __init__(self) -> None:
        super().__init__(
            agent_type="claude",
            framework="mngr-claude",
            agent_args_builder=_build_agent_args,
            status_extractor=_extract_status,
            assistant_text_extractor=_extract_assistant_text,
        )
