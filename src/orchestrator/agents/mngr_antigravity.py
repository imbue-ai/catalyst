from typing import Any, Dict, List, Optional

from .mngr_runner import MngrAgentRunner, TurnCompletion

# Source under the agent's events/ dir where mngr_antigravity's
# common_transcript.sh writes the agent-agnostic transcript. Distinct from
# mngr_claude's `claude/common_transcript`.
_ANTIGRAVITY_TRANSCRIPT_SOURCE = "antigravity/common_transcript"


def _build_agent_args(model: Optional[str]) -> List[str]:
    # The Antigravity CLI (`agy`) exposes no `--model` flag, so the model
    # selection ai-scientist threads through for Claude has no CLI surface
    # here -- agy uses its account default. Auto-approval
    # (`--dangerously-skip-permissions`) and workspace trust are handled by
    # the mngr_antigravity plugin via the `[agent_types.antigravity]`
    # settings (`auto_allow_permissions` / `auto_dismiss_dialogs`), so there
    # are no per-call agent args to add.
    del model
    return []


def _extract_assistant_text(event: Dict[str, Any]) -> Optional[str]:
    if event.get("type") != "assistant_message":
        return None
    text = event.get("text")
    if isinstance(text, str) and text:
        return text
    return None


def _extract_status(event: Dict[str, Any]) -> Optional[str]:
    # agy's common transcript emits each PLANNER_RESPONSE as an
    # assistant_message: the final answer carries `text` and no tool_calls,
    # while a tool-using step carries empty `text` and the requested
    # tool_calls. Surface the text when present, otherwise name the tool so
    # the dashboard shows live progress during tool runs.
    if event.get("type") != "assistant_message":
        return None
    text = event.get("text")
    if isinstance(text, str) and text.strip():
        return " ".join(text.split())
    for call in event.get("tool_calls", []) or []:
        tool_name = call.get("tool_name")
        if isinstance(tool_name, str) and tool_name:
            return f"Running {tool_name}"
    return None


class MngrAntigravityAgentRunner(MngrAgentRunner):
    def __init__(self) -> None:
        super().__init__(
            agent_type="antigravity",
            framework="mngr-antigravity",
            agent_args_builder=_build_agent_args,
            status_extractor=_extract_status,
            assistant_text_extractor=_extract_assistant_text,
            transcript_source=_ANTIGRAVITY_TRANSCRIPT_SOURCE,
            turn_completion=TurnCompletion.TRANSCRIPT_IDLE,
        )
