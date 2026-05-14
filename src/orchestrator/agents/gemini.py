import json
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
    # on an assistant_message event. The exact field carrying the summary
    # is the plugin's choice: the common transcript uses `input_preview`
    # (a JSON-encoded string), while a structured `parameters` dict is
    # the natural alternative. Try both rather than coupling tightly to
    # one shape.
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
        preview = call.get("input_preview")
        if isinstance(preview, str):
            try:
                parsed = json.loads(preview)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                summary = parsed.get("summary")
                if isinstance(summary, str) and summary.strip():
                    return summary
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
