---
name: propose-experiment
description: "Design and propose the next single experiment to run, generating a proposal description and a runnable companion script."
argument-hint: "interpretations log ID (e.g. I_20260616_123456_abcdef)"
---

# Propose Experiment

This skill is used to design and propose a single, high-value, and cost-effective next experiment to advance the research goal, providing a descriptive proposal and a companion executable Python script.

## Mandate
- Propose a single, focused experiment that resolves a key knowledge gap, validates an assumption or hypothesis, or tests a promising optimization in the interpretations log.
- At the very beginning of experimentation (i.e. if the current interpretations log is still close to empty), it might be best to establish some baselines before trying to explore paths towards the goal.
- Generally, try to propose an experiment that provides valuable information for moving towards the optimization goal *in the long run*. Notably, this doesn't mean that each individual experiment needs to move towards the goal directly. Rather, prioritize experiments that facilitate learning and exploration and which may help you later on by testing different directions, key assumptions, or ruling out unpromising paths.
- All experiment files and companion scripts must be structured so they can run fully self-contained by executing the `script.py` file.

## Input
Arguments: $ARGUMENTS

The arguments contain an interpretations log ID (like `I_...`). Parse this ID from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for the input context, one for your own output:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp propose-experiment-context-XXXX`
- `OUTPUT_DIR`: `mktemp -d -p ./tmp propose-experiment-output-XXXX`

Run this command to populate the context, which retrieves the interpretations log from the database:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type propose-experiment \
    --target_folder <CONTEXT_DIR> \
    --from_interpretations <I_ID>
```

- `<CONTEXT_DIR>/interpretations/` — contains `interpretations.md` (read-only historical log).
- `<OUTPUT_DIR>/` — write your proposal files (`proposal.md` and `script.py`) here.

---

## Execution Steps

1. **Context Checkout**: Run the `create_context` bash command above to retrieve the interpretations log from the database.
2. **Review Historical Log**: Read `<CONTEXT_DIR>/interpretations/interpretations.md` to identify knowledge gaps, uncertainties, or promising parameters.
3. **Design Experiment Proposal**: Write a document named `proposal.md` (this exact filename is required) in your `<OUTPUT_DIR>/` detailing:
   - **Motivation**: Why this experiment is important and what specific question/optimization it is testing.
   - **Experimental Setup**: Methodology, parameters, baseline, and comparison group.
   - **Expected Outputs**: Expected files, plots, metrics, or CSVs.
   - **Estimated Cost/Runtime**: Estimated runtime for performing the experiment.
4. **Write Companion Script**: Write a companion, fully self-contained Python script named `script.py` (this exact filename is required) in the same `<OUTPUT_DIR>/` folder.
   - The script must hard-code all parameters and not rely on command-line arguments or environment variables.
   - It must write all outputs (such as plots, logs, and metrics) directly to its current working directory.
   - It can import shared helper libraries or scripts in the workspace, but must not depend on files that are only present in a temporary folder.
5. **Store Results**: Persist the proposal and script to the database:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results \
       --from_agent_type propose-experiment \
       --from_folder <OUTPUT_DIR> \
       --parent_interpretations <I_ID>
   ```
   *Note down the returned proposal ID (e.g., `O_20260616_123456_abcdef`) as the result of this skill.*
