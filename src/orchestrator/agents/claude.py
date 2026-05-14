import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from .mngr_runner import MngrAgentRunner

# Appended to Claude's system prompt for every ai-scientist step. Tracks any
# friction Claude hits while following a skill so we can investigate later.
_ADDITIONAL_SYSTEM_PROMPT = (
    "If you encounter any issues with following the instructions in a skill, "
    "or run into issues with your execution environment (e.g. missing permission, "
    "error while running a pre-provided script, etc.), please take a second to "
    "append a short, one-line issue description to `./tmp/agent_friction_log.txt`."
)

# Relative to the agent's work_dir (== env_folder). Written by ClaudeAgentRunner
# before each `mngr create` so claude can read it via --append-system-prompt-file.
# We use the file flag rather than --append-system-prompt <string> because
# mngr_claude composes the agent's startup as a single shell command pasted into
# the agent's tmux pane. A long inline string (especially with backticks) gets
# mangled by zsh's line editor / autosuggest plugins, the paste-confirm hook
# never sees the expected pane content, and the agent fails to start.
_SYSTEM_PROMPT_REL = ".aisci_system_prompt.txt"


def _build_agent_args(model: Optional[str]) -> List[str]:
    args = [
        "--dangerously-skip-permissions",
        "--verbose",
        "--append-system-prompt-file",
        _SYSTEM_PROMPT_REL,
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

    def run(
        self,
        task_id: str,
        prompt: str,
        env_folder: str,
        model: Optional[str] = None,
        tx_id: Optional[str] = None,
        stage: Optional[str] = None,
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        prompt_path = os.path.join(os.path.abspath(env_folder), _SYSTEM_PROMPT_REL)
        os.makedirs(os.path.dirname(prompt_path) or ".", exist_ok=True)
        with open(prompt_path, "w") as f:
            f.write(_ADDITIONAL_SYSTEM_PROMPT)
        return super().run(
            task_id=task_id,
            prompt=prompt,
            env_folder=env_folder,
            model=model,
            tx_id=tx_id,
            stage=stage,
            on_session_id=on_session_id,
            on_status=on_status,
        )
