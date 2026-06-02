from .mngr_runner import MngrAgentRunner, TurnCompletion

# `--dangerously-skip-permissions` is added by the mngr_claude plugin when
# `auto_allow_permissions = true` (see `.mngr/settings.toml`). The
# friction-log instruction lives in `BASE_CLAUDE_MD` (auto-loaded by Claude
# from the work_dir's `CLAUDE.md`), so the runner contributes nothing more
# than `--model` and the model name.


class MngrClaudeAgentRunner(MngrAgentRunner):
    def __init__(self) -> None:
        super().__init__(
            agent_type="claude",
            framework="mngr-claude",
            transcript_source="claude/common_transcript",
            turn_completion=TurnCompletion.STOP_HOOK,
            model_flag="--model",
            # Force synchronous subagent execution. Claude Code (v2.1.4+)
            # may otherwise run subagents asynchronously, letting the parent
            # emit `end_turn` and finish its turn while subagents are still
            # running in the background. Catalyst's contract is "each step's
            # parent agent emits final JSON consumed by the next step",
            # which requires synchronous subagents so the parent has the
            # subagent results before composing its final message. See
            # https://claudelog.com/faqs/what-is-disable-background-tasks-in-claude-code/
            extra_env={"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"},
        )
