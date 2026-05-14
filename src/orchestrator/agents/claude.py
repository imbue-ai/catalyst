from typing import Any, Dict, List, Optional

from .mngr_runner import MngrAgentRunner

# Appended to Claude's system prompt for every ai-scientist step. Tracks any
# friction Claude hits while following a skill so we can investigate later.
_ADDITIONAL_SYSTEM_PROMPT = (
    "If you encounter any issues with following the instructions in a skill, "
    "or run into issues with your execution environment (e.g. missing permission, "
    "error while running a pre-provided script, etc.), please take a second to "
    "append a short, one-line issue description to `./tmp/agent_friction_log.txt`."
)


def _build_agent_args(model: Optional[str]) -> List[str]:
    args = [
        "--dangerously-skip-permissions",
        "--verbose",
        "--append-system-prompt",
        _ADDITIONAL_SYSTEM_PROMPT,
    ]
    if model:
        args.extend(["--model", model])
    return args


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


class ClaudeAgentRunner(MngrAgentRunner):
    def __init__(self) -> None:
        super().__init__(
            agent_type="claude",
            framework="claude",
            agent_args_builder=_build_agent_args,
            status_extractor=_extract_status,
            assistant_text_extractor=_extract_assistant_text,
        )
