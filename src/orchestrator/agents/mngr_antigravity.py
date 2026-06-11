from .mngr_runner import MngrAgentRunner, TurnCompletion


class MngrAntigravityAgentRunner(MngrAgentRunner):
    def __init__(self) -> None:
        super().__init__(
            agent_type="antigravity",
            framework="mngr-antigravity",
            transcript_source="antigravity/common_transcript",
            turn_completion=TurnCompletion.WAITING_STATE,
            # Run agy under its terminal sandbox. We pair this with a
            # permissions policy (NOT `--dangerously-skip-permissions`) in
            # `.mngr/settings.toml`'s `[agent_types.antigravity]`:
            # `toolPermission = "proceed-in-sandbox"` auto-proceeds every tool
            # call inside the sandbox, and `deny = ["unsandboxed"]` refuses
            # any escape. This is what avoids agy bug #36 -- combining
            # `--dangerously-skip-permissions` with `--sandbox` silently
            # disables the sandbox -- so we keep `auto_allow_permissions =
            # false` and let the policy do the auto-approval while `--sandbox`
            # stays enforced.
            # https://github.com/google-antigravity/antigravity-cli/issues/36
            #
            # `--print-timeout` only matters in `-p` mode, which mngr doesn't
            # use, so we don't pass it.
            agent_args=("--sandbox",),
            #
            # `--model` accepts the name as shown in agy's in-session
            # `/model` menu (run `agy models` for the list), e.g.
            # "Gemini 3.5 Flash (Low)" or "Claude Sonnet 4.6 (Thinking)".
            model_flag="--model",
            # Match the direct agy runner: don't let agy phone home for an
            # update mid-task (orchestrator/agents/agy.py sets the same).
            extra_env={"AGY_CLI_DISABLE_AUTO_UPDATE": "true"},
        )
