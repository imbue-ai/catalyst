---
name: execute-proposal
description: "Coordinate the execution of a selected experiment proposal, delegating to the run-experiment skill and returning the stored experiment ID."
argument-hint: "proposal ID (e.g. O_20260616_123456_abcdef)"
---

# Execute Proposal

This skill is used to coordinate and execute a single selected experiment proposal by creating a workspace, copying the proposal's script and description, executing it through the standard `run-experiment` wrapper, and recording the final experiment ID.

## Mandate
- Run the experiment exactly as designed in the selected proposal. Do not modify the parameters or logic of the companion script unless necessary to fix runtime issues.
- All actual experiment executions must go through the standard `run-experiment` wrapper. Never run the Python script directly.

## Input
Arguments: $ARGUMENTS

The arguments contain a single proposal ID (like `O_20260616_...`). Parse this ID from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for the input context, one for your own output:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp execute-proposal-context-XXXX`
- `OUTPUT_DIR`: `mktemp -d -p ./tmp execute-proposal-output-XXXX`

Run this command to populate the context, which retrieves the proposal files from the database:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type execute-proposal \
    --target_folder <CONTEXT_DIR> \
    --from_proposal <PROPOSAL_ID>
```

- `<CONTEXT_DIR>/proposal/` — contains the read-only proposal files: `proposal.md` and the `script.py` file which forms the entrypoint to the experiment. Might contain additional Python files and dependencies for running the experiment.
- `<OUTPUT_DIR>/` — write your execution summary and metadata here.

---

## Execution Steps

1. **Context Checkout**: Run the `create_context` bash command above to retrieve the selected proposal and companion script from the database.
2. **Copy Proposal Files**: Copy all files from `<CONTEXT_DIR>/proposal/` into `<OUTPUT_DIR>/`. The `proposal.md` will serve as the `description.md` for the experiment execution, and should be renamed as such.
2. **Execute Experiment**: Invoke the `run-experiment` skill to execute the proposal script using the run_experiment.py wrapper. Use a copy of the existing `proposal.md` as the `description.md` for the experiment, and pass the output directory as the experiment folder.
3. **Check Results**: The runner will execute the script, capture all outputs, save them to the database, and print a unique experiment ID (e.g. `X_20260616_123456_abcdef`) at the end of its stdout/stderr. Parse this experiment ID from the runner's output.
4. **Fix Bugs**: If the experiment execution fails due to a code or runtime bug, attempt to fix up the code in your `<OUTPUT_DIR>` and run the experiment again using the `run-experiment` procedure.
5. **Report Results**: Note down the returned experiment ID as the result of this skill.
