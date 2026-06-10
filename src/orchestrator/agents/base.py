import json
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Tuple
import os
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
            env["CATALYST_SCORING_CORRECTNESS_WEIGHT"] = str(
                theory_scoring_weights.correctness_weight
            )
            env["CATALYST_SCORING_POWER_WEIGHT"] = str(
                theory_scoring_weights.power_weight
            )
            env["CATALYST_SCORING_ADHERENCE_WEIGHT"] = str(
                theory_scoring_weights.adherence_weight
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
