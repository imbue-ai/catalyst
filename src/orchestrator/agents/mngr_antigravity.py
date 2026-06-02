from .mngr_runner import MngrAgentRunner, TurnCompletion


class MngrAntigravityAgentRunner(MngrAgentRunner):
    def __init__(self) -> None:
        super().__init__(
            agent_type="antigravity",
            framework="mngr-antigravity",
            transcript_source="antigravity/common_transcript",
            turn_completion=TurnCompletion.WAITING_STATE,
            # `--sandbox` matches the isolation the direct `agy` runner
            # uses (orchestrator/agents/agy.py): terminal restrictions so
            # a research step can't write outside its workspace ($TMPDIR,
            # ~/.gemini, etc.). Under mngr the agent's work_dir is the
            # task env_folder (exposed to agy via the plugin's workspace
            # symlink), so sandboxed writes still land in the right place.
            #
            # agy has no `--model` flag, so `model_flag` is left unset and
            # agy uses its account default. `--dangerously-skip-permissions`
            # is added by the mngr_antigravity plugin via
            # `auto_allow_permissions = true` in `.mngr/settings.toml`.
            agent_args=("--sandbox",),
            # Match the direct agy runner: don't let agy phone home for an
            # update mid-task (orchestrator/agents/agy.py sets the same).
            extra_env={"AGY_CLI_DISABLE_AUTO_UPDATE": "true"},
        )
