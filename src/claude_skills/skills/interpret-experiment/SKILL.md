---
name: interpret-experiment
description: "Interpret the results of a newly run experiment and append the findings as a new experiment section to the interpretations log."
argument-hint: "interpretations log ID and experiment ID (e.g. I_20260616_123456_abcdef X_20260616_123456_abcdef)"
---

# Interpret Experiment

This skill is used to review the results of a completed experiment and append its interpretations and conclusions to the central interpretations log.

## Mandate
- Keep interpretations objective and strictly supported by empirical observations. Avoid over-generalizing or jumping to unsupported conclusions.
- Do not modify or overwrite any historical sections of the interpretations log; only append the new experiment section under a new header.

## Input
Arguments: $ARGUMENTS

The arguments contain an interpretations log ID (like `I_...`) and an experiment ID (like `X_...`). Parse both IDs from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for the input context, one for your own output:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp interpret-experiment-context-XXXX`
- `OUTPUT_DIR`: `mktemp -d -p ./tmp interpret-experiment-output-XXXX`

Run this command to populate the context, which retrieves the interpretations log and experiment results from the database:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type interpret-experiment \
    --target_folder <CONTEXT_DIR> \
    --from_interpretations <I_ID> \
    --from_experiment <X_ID>
```

Initialize your output directory with the current interpretations log file:
```bash
cp -r "<CONTEXT_DIR>/interpretations/"* "<OUTPUT_DIR>/"
```

- `<CONTEXT_DIR>/interpretations/` — contains `interpretations.md` (read-only historical log).
- `<CONTEXT_DIR>/experiment/` — contains the experiment folder with `description.md` and all generated plots, logs, and CSV outputs.
- `<OUTPUT_DIR>/` — contains `interpretations.md` which you will modify by appending the new experiment's interpretations.

---

## Execution Steps

1. **Context Checkout**: Run the `create_context` bash command above to retrieve the historical interpretations log and new experiment results.
2. **Review Historical Log**: Read `<CONTEXT_DIR>/interpretations/interpretations.md` to understand previous findings and current context.
3. **Review Experiment Results**: Read `<CONTEXT_DIR>/experiment/description.md` and carefully inspect the generated files (plots, CSVs, logs, etc.) in `<CONTEXT_DIR>/experiment/`.
4. **Draft Interpretations**: Draft a new section summarizing this experiment:
   - State clearly what was tested and what parameter values were used.
   - Describe the empirical observations (numbers, trends, anomaly detections, etc.).
   - Detail the conclusions and interpretations drawn from these observations, as well as any remaining open questions that would be helpful to resolve to further the research goal.
   - As part of your interpretation, you may perform mathematical derivations as needed, or form new hypotheses to investigate in future experiments.
5. **Update Log**: Append this new section to `<OUTPUT_DIR>/interpretations.md` under a new header (e.g. `## Experiment <X_ID>: <Title>`).
6. **Store Results**: Persist the updated interpretations log to the database:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results \
       --from_agent_type interpret-experiment \
       --from_folder <OUTPUT_DIR> \
       --parent_interpretations <I_ID>
   ```
   *Replace `<I_ID>` with the ID of the input interpretations log, ensuring child-to-parent lineage mapping.*
