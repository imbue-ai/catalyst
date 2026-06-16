---
name: refine-interpretations
description: "Address inconsistency reports by re-evaluating contradictory conclusions and updating the interpretations log accordingly."
argument-hint: "interpretations log ID and review ID(s) (e.g. I_20260616_123456_abcdef R_20260616_123456_abcdef)"
---

# Refine Interpretations

This skill is used to address inconsistency reports, re-evaluating contradictory findings or gaps highlighted in review reports, and updating the interpretations log to restore logical coherence.

## Mandate
- Resolve every inconsistency identified in the input review reports.
- Do not delete experimental evidence; refine claims, clarify parameter ranges, or move unresolved issues into an "Open Questions" section under the respective experiment(s).

## Input
Arguments: $ARGUMENTS

The arguments contain an interpretations log ID (like `I_...`) and one or more review IDs (like `R_...`). Parse all IDs from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for the input context, one for your own output:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp refine-interpretations-context-XXXX`
- `OUTPUT_DIR`: `mktemp -d -p ./tmp refine-interpretations-output-XXXX`

Run this command to populate the context, which retrieves the interpretations log and the inconsistency review reports:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type refine-interpretations \
    --target_folder <CONTEXT_DIR> \
    --from_interpretations <I_ID> \
    --from_review <REVIEW_ID_1> [--from_review <REVIEW_ID_2> ...]
```

Initialize your output directory with the current interpretations log file:
```bash
cp -r "<CONTEXT_DIR>/interpretations/"* "<OUTPUT_DIR>/"
```

- `<CONTEXT_DIR>/interpretations/` — contains `interpretations.md` (read-only historical log).
- `<CONTEXT_DIR>/reviews/<review_id>/` — contains each review report with `review.md`.
- `<OUTPUT_DIR>/` — contains `interpretations.md` which you will modify to resolve inconsistencies.

---

## Execution Steps

1. **Context Checkout**: Run the `create_context` bash command above to retrieve the interpretations log and the review reports from the database.
2. **Review Reports**: Read all review reports in `<CONTEXT_DIR>/reviews/*/review.md` to understand the flagged contradictions or gaps.
3. **Formulate Resolutions**: Re-evaluate the contradictory findings in `interpretations.md` and formulate logical resolutions (such as qualifying assertions, clarifying boundary conditions, or adding unresolved issues to an "Open Questions" section under the respective experiment(s)).
4. **Update Log**: Apply your refinements to `<OUTPUT_DIR>/interpretations.md` (this exact filename is required).
5. **Store Results**: Persist the refined interpretations log to the database:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results \
       --from_agent_type refine-interpretations \
       --from_folder <OUTPUT_DIR> \
       --parent_interpretations <I_ID>
   ```
   *Note down the returned interpretations log ID.*
