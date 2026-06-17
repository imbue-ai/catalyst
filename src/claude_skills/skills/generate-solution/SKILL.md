---
name: generate-solution
description: "Formulate, draft, or refine a candidate solution to the overall research goal based on findings in the interpretations log."
argument-hint: "interpretations log ID and optional previous solution ID (e.g. I_20260616_123456_abcdef [U_20260616_123456_abcdef])"
---

# Generate Solution

You are an expert scientific agent. Your goal is to draft or refine a high-quality candidate solution to the overall research goal, leveraging the latest insights, verified parameters, and empirical findings documented in the central interpretations log.

## Mandate
- Formulate or refine the candidate solution so that it best addresses the overall research goal.
- Ground all recommendations (architectures, hyperparameter values, schedules, or methodology) strictly on the empirical observations and experiment IDs documented in the interpretations log.
- Do not make speculative recommendations or suggest configurations that have not been tested or are not supported by the evidence in the interpretations log.
- If a previous candidate solution is provided, perform a precise comparison between the current interpretations log and the historical interpretations log associated with the previous solution to identify what exact new insights, parameter ranges, or findings have been added or updated since the previous solution draft. Use these new findings to refine and improve the solution.

## Input
Arguments: $ARGUMENTS

The arguments contain an interpretations log ID (like `I_20260616_...`) and optionally a previous solution ID (like `U_20260616_...`). Parse both IDs from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for input context, one for your own output:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp generate-solution-context-XXXX`
- `OUTPUT_DIR`: `mktemp -d -p ./tmp generate-solution-output-XXXX`

Run this command to populate the context, which retrieves the necessary files from the database:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type generate-solution \
    --target_folder <CONTEXT_DIR> \
    --from_interpretations <I_ID> \
    [--from_solution <U_ID>]
```

If a previous solution ID (`<U_ID>`) is provided, initialize the output folder with the previous solution draft files so you can incrementally edit them:
```bash
cp -r "<CONTEXT_DIR>/previous_solution/"* "<OUTPUT_DIR>/"
```

### Context and Output Layout
- `<CONTEXT_DIR>/interpretations/` — contains `interpretations.md` (read-only current interpretations log).
- `<CONTEXT_DIR>/previous_solution/` — (optional, if `<U_ID>` was specified) contains the previous solution draft `solution.md`.
- `<CONTEXT_DIR>/previous_interpretations/` — (optional, if `<U_ID>` was specified and has a registered parent interpretations log) contains the historical interpretations log `interpretations.md` that was used to draft that previous solution.
- `<OUTPUT_DIR>/` — write your drafted or refined candidate solution `solution.md` here.

---

## Execution Steps

1. **Context Checkout**: Run the `create_context` command above to check out the current interpretations log and (if available) the previous solution draft and its historical interpretations log.
2. **Review Current Interpretations**: Read `<CONTEXT_DIR>/interpretations/interpretations.md` to collect all verified facts, parameters, and proven configurations.
3. **Analyze Solution History**: If a previous solution is available:
   - Compare `<CONTEXT_DIR>/interpretations/interpretations.md` with `<CONTEXT_DIR>/previous_interpretations/interpretations.md` to identify the exact new insights, parameter ranges, or experimental outcomes added or updated since the previous solution draft.
   - Read `<CONTEXT_DIR>/previous_solution/solution.md` to understand the previous architecture and recommendations.
4. **Draft/Refine Solution**: Formulate or edit the candidate solution in a file named `solution.md` (this exact filename is required) under `<OUTPUT_DIR>/solution.md`:
   - It should clearly address the overall research goal.
   - It should describe the recommended architecture, hyperparameter values, scheduling, or methodology in detail.
   - It must back up all recommendations with specific empirical evidence and cite the relevant experiment IDs (e.g. `X_...`) documented in the interpretations log.
5. **Store Results**: Persist the drafted or refined solution to the database:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results \
       --from_agent_type generate-solution \
       --from_folder <OUTPUT_DIR> \
       --parent_interpretations <I_ID> \
       [--parent_solution <U_ID>]
   ```
   *Replace `<I_ID>` with the current interpretations log ID, and `<U_ID>` with the previous solution ID if refining.*
   *Note down the returned solution ID (e.g., `U_20260616_123456_abcdef`) as the result of this skill, together with a brief note on what improvements were introduced, and include both in your final message.*
