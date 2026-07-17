from typing import Dict, Any, Optional, Tuple, Callable
from orchestrator.agents.base import EXPERIMENT_TIMEOUT_SECS, write_claude_settings

from .mngr_runner import MngrAgentRunner, TurnCompletion

# Per-tool permission prompts are auto-allowed by the mngr_claude plugin's
# `PermissionRequest` hook when `auto_allow_permissions = true` (see
# `.mngr/settings.toml`).


class MngrClaudeAgentRunner(MngrAgentRunner):
    def __init__(self, disable_sandboxing: bool = False) -> None:
        bash_timeout_ms = (
            EXPERIMENT_TIMEOUT_SECS * 1000 + 5 * 60 * 1000
        )  # The experiment timeout in milliseconds plus a 5 minute safety buffer.

        super().__init__(
            agent_type="claude",
            framework="mngr-claude",
            transcript_source="claude/common_transcript",
            turn_completion=TurnCompletion.STOP_HOOK,
            disable_sandboxing=disable_sandboxing,
            model_flag="--model",
            effort_flag="--effort",
            extra_env={
                # Force synchronous subagent execution. Claude Code (v2.1.4+)
                # may otherwise run subagents asynchronously, letting the
                # parent emit `end_turn` and finish its turn while subagents
                # are still running in the background. Catalyst's contract is
                # "each step's parent agent emits final JSON consumed by the
                # next step", which requires synchronous subagents so the
                # parent has the subagent results before composing its final
                # message. See
                # https://claudelog.com/faqs/what-is-disable-background-tasks-in-claude-code/
                "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
                # Keep bash invocations rooted at the work_dir (the env_folder)
                # rather than letting `cd` calls in one tool invocation drift
                # the cwd for the next one. Matches the direct claude runner.
                "CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR": "1",
                # Disable auto memory
                "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
                # Bump bash timeouts well past Claude Code's defaults so a
                # long-running experiment doesn't get killed mid-step.
                "BASH_DEFAULT_TIMEOUT_MS": str(bash_timeout_ms),
                "BASH_MAX_TIMEOUT_MS": str(bash_timeout_ms),
            },
        )

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
        write_claude_settings(env_folder, self.disable_sandboxing, include_stop_hook=True)
        return super().run(
            task_id=task_id,
            prompt=prompt,
            env_folder=env_folder,
            stage=stage,
            common_environment_variables=common_environment_variables,
            model=model,
            effort=effort,
            on_session_id=on_session_id,
            on_status=on_status,
        )
