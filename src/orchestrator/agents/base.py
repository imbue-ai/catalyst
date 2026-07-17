import json
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Tuple
import os
import threading
from context_manager import DEFAULT_DB_DIR
from ..models import TheoryScoringWeights


EXPERIMENT_TIMEOUT_SECS = int(os.getenv("CATALYST_EXPERIMENT_TIMEOUT_SECS", 30 * 60))
EXPERIMENT_RLIMIT_AS = int(
    os.getenv("CATALYST_EXPERIMENT_RLIMIT_AS", 12 * 1024 * 1024 * 1024)
)
AGENT_TIMEOUT_SECS = (
    16 * EXPERIMENT_TIMEOUT_SECS + 60 * 60
)  # 16x the experiment timeout plus 1 hour


def parse_json_result(raw_result: Any) -> Optional[Dict[str, Any]]:
    """Extract a JSON object out of an agent's freeform final assistant text.

    Catalyst's skills are prompted to "output JSON as your final message"
    but the wrapping varies: sometimes a fenced ```json block, sometimes
    raw text containing braces.
    """
    if isinstance(raw_result, dict):
        return raw_result

    text = str(raw_result)

    json_blocks = re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_blocks:
        try:
            return json.loads(json_blocks[-1])
        except json.JSONDecodeError:
            pass

    last_brace = text.rfind("}")
    while last_brace != -1:
        balance = 0
        for i in range(last_brace, -1, -1):
            if text[i] == "}":
                balance += 1
            elif text[i] == "{":
                balance -= 1
                if balance == 0:
                    obj_str = text[i : last_brace + 1]
                    try:
                        data = json.loads(obj_str)
                        if isinstance(data, dict):
                            return data
                    except json.JSONDecodeError:
                        break

        last_brace = text.rfind("}", 0, last_brace)

    return None


class AgentRunner(ABC):
    def build_common_environment_variables(
        self,
        env_folder: str,
        tx_id: Optional[str] = None,
        theory_scoring_weights: Optional[TheoryScoringWeights] = None,
    ) -> Dict[str, str]:
        abs_env_folder = os.path.abspath(env_folder)
        env = {
            "UV_CACHE_DIR": os.path.join(abs_env_folder, "tmp/uv_cache"),
            "CATALYST_DB_PATH": os.path.join(abs_env_folder, DEFAULT_DB_DIR),
            "MPLCONFIGDIR": os.path.join(abs_env_folder, "tmp/matplotlib_cache"),
        }
        if tx_id:
            env["CONTEXT_TRANSACTION_ID"] = tx_id
        if theory_scoring_weights is not None:
            if theory_scoring_weights.correctness_weight is not None:
                env["CATALYST_SCORING_CORRECTNESS_WEIGHT"] = str(
                    theory_scoring_weights.correctness_weight
                )
            if theory_scoring_weights.power_weight is not None:
                env["CATALYST_SCORING_POWER_WEIGHT"] = str(
                    theory_scoring_weights.power_weight
                )
            if theory_scoring_weights.adherence_weight is not None:
                env["CATALYST_SCORING_ADHERENCE_WEIGHT"] = str(
                    theory_scoring_weights.adherence_weight
                )
            if theory_scoring_weights.past_performance_weight is not None:
                env["CATALYST_SCORING_PAST_PERFORMANCE_WEIGHT"] = str(
                    theory_scoring_weights.past_performance_weight
                )
            if theory_scoring_weights.future_potential_weight is not None:
                env["CATALYST_SCORING_FUTURE_POTENTIAL_WEIGHT"] = str(
                    theory_scoring_weights.future_potential_weight
                )
            env["CATALYST_EXPERIMENT_TIMEOUT_SECS"] = str(EXPERIMENT_TIMEOUT_SECS)
            env["CATALYST_EXPERIMENT_RLIMIT_AS"] = str(EXPERIMENT_RLIMIT_AS)
        return env

    @abstractmethod
    def run(
        self,
        task_id: str,
        prompt: str,
        env_folder: str,
        stage: str,
        common_environment_variables: Dict[str, str],
        model: Optional[str] = None,
        effort: Optional[str] = None,
        on_session_id: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Runs the agent and returns (json_output, session_id, error).

        `session_id` is the identifier used by the dashboard's "Inspect
        Agent" panel. The direct `claude` / `gemini` runners write the CLI
        session UUID here (the direct `agy` runner has none); the
        `mngr-claude`/`mngr-antigravity` runners write the mngr agent name
        (e.g. "cata-abcd1234-..."). The frontend picks the right `Inspect
        Agent` command from the framework type.

        `stage` is the workflow stage name (e.g. "write-theory"). The
        mngr runners use it to label and name their agents; the direct
        runners ignore it.
        """
        pass


_claude_settings_lock = threading.Lock()


def write_claude_settings(
    env_folder: str, disable_sandboxing: bool, include_stop_hook: bool
) -> None:
    """Dynamically writes or updates the .claude/settings.json file inside env_folder."""
    settings_dir = os.path.join(os.path.abspath(env_folder), ".claude")
    os.makedirs(settings_dir, exist_ok=True)
    settings_path = os.path.join(settings_dir, "settings.json")

    # 1. Build the expected settings dict
    if disable_sandboxing:
        sandbox_config = {"enabled": False}
    else:
        sandbox_config = {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "network": {"allowedDomains": ["*"]},
            "filesystem": {"allowWrite": ["~/.mngr-catalyst/agents"]},
        }

    new_settings = {
        "sandbox": sandbox_config,
        "permissions": {"allow": ["WebSearch(*)", "WebFetch(*)", "Bash(*)"]},
    }

    if include_stop_hook:
        new_settings["hooks"] = {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": '[ -z "${MNGR_AGENT_STATE_DIR:-}" ] && exit 0; [ -n "${MNGR_CLAUDE_SUBAGENT_PROXY_CHILD:-}" ] && exit 0; mkdir -p "$MNGR_AGENT_STATE_DIR/events/mngr/turn_complete" && printf \'{"timestamp":"%s","event_id":"turn_end-%s","type":"turn_end","source":"mngr/turn_complete"}\\n\' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(uuidgen 2>/dev/null || od -An -N16 -tx1 /dev/urandom | tr -d \' \\n\')" >> "$MNGR_AGENT_STATE_DIR/events/mngr/turn_complete/events.jsonl"',
                        }
                    ]
                }
            ]
        }

    # 2. Acquire the process-level thread lock and system-level file lock
    with _claude_settings_lock:
        # Read existing settings and check if they are identical
        existing_settings = None
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                existing_settings = json.load(f)

        # If current state of file is already up to date, it should not be rewritten
        if existing_settings != new_settings:
            # Write to a temp file in the same directory first, then rename it
            temp_settings_path = settings_path + ".tmp"
            with open(temp_settings_path, "w", encoding="utf-8") as f:
                json.dump(new_settings, f, indent=2)
                f.write("\n")
            os.replace(temp_settings_path, settings_path)
