from typing import Any, Dict, List, Optional

from .mngr_runner import MngrAgentRunner


def _build_agent_args(model: Optional[str]) -> List[str]:
    # mngr_gemini owns the standard `--approval-mode yolo --sandbox
    # --skip-trust` invocation; only the model selection lives here.
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
    # mngr_gemini surfaces Gemini's `update_topic` tool as a tool_call entry
    # on an assistant_message event with the summary in a `parameters` dict.
    # If the actual contract turns out to deliver the summary through a
    # different field (e.g. claude/common_transcript's `input_preview`
    # JSON-encoded string), the raise below trips so we pick the real shape
    # and delete this branch instead of leaving a guess in production.
    if event.get("type") != "assistant_message":
        return None
    for call in event.get("tool_calls", []) or []:
        if call.get("tool_name") != "update_topic":
            continue
        params = call.get("parameters")
        if isinstance(params, dict):
            summary = params.get("summary")
            if isinstance(summary, str) and summary.strip():
                return summary
        raise NotImplementedError(
            "update_topic tool_call has no `parameters` dict; confirm the "
            "mngr_gemini contract and replace this extractor with the actual "
            "shape (likely `input_preview` JSON). tool_call=%r" % (call,)
        )
    return None


class GeminiAgentRunner(MngrAgentRunner):
    def __init__(self) -> None:
        super().__init__(
            agent_type="gemini",
            framework="gemini",
            agent_args_builder=_build_agent_args,
            status_extractor=_extract_status,
            assistant_text_extractor=_extract_assistant_text,
        )
