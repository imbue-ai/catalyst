from .mngr_runner import MngrAgentRunner, TurnCompletion


class MngrAntigravityAgentRunner(MngrAgentRunner):
    def __init__(self) -> None:
        super().__init__(
            agent_type="antigravity",
            framework="mngr-antigravity",
            transcript_source="antigravity/common_transcript",
            turn_completion=TurnCompletion.WAITING_STATE,
            # `--sandbox` is *intentionally* omitted here even though the
            # direct `agy` runner sets it. agy bug #36 (combining
            # `--dangerously-skip-permissions` with `--sandbox` is broken)
            # means our `auto_allow_permissions = true` setting -- which
            # the mngr_antigravity plugin implements by adding
            # `--dangerously-skip-permissions` -- silently bypasses
            # sandboxing if we also set `--sandbox`. Dropping `--sandbox`
            # here makes the lack-of-isolation explicit rather than fake.
            # https://github.com/google-antigravity/antigravity-cli/issues/36
            #
            # agy has no `--model` flag, so `model_flag` is left unset and
            # agy uses its account default. `--dangerously-skip-permissions`
            # is added by the mngr_antigravity plugin via
            # `auto_allow_permissions = true` in `.mngr/settings.toml`.
            #
            # `--print-timeout 6h` matches the direct `agy` runner -- agy's
            # default print-timeout (5m) is far too short for a research
            # turn that runs experiments.
            agent_args=("--print-timeout", "6h"),
            # Match the direct agy runner: don't let agy phone home for an
            # update mid-task (orchestrator/agents/agy.py sets the same).
            extra_env={"AGY_CLI_DISABLE_AUTO_UPDATE": "true"},
        )
