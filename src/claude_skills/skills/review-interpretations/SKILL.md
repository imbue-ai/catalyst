---
name: review-interpretations
description: "Review an interpretations log, checking for potential contradictions, gaps, or inconsistencies introduced by the latest experiment, and document them."
argument-hint: "interpretations log ID (e.g. I_20260616_123456_abcdef)"
---

# Review Interpretations

This skill is used to perform a critical review of the entire interpretations log, checking for logical contradictions, unjustified assumptions, or key gaps introduced by recent experimental results.

## Mandate
- Critically evaluate recent interpretations against historical ones. Do not let contradictions or logical inconsistencies slip through.
- Document every potential issue clearly, referencing specific experiment IDs and sections in conflict.

## Input
Arguments: $ARGUMENTS

The arguments contain an interpretations log ID (like `I_...`). Parse this ID from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for the input context, one for your own output:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp review-interpretations-context-XXXX`
- `OUTPUT_DIR`: `mktemp -d -p ./tmp review-interpretations-output-XXXX`

Run this command to populate the context, which retrieves the interpretations log from the database:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type review-interpretations \
    --target_folder <CONTEXT_DIR> \
    --from_interpretations <I_ID>
```

- `<CONTEXT_DIR>/interpretations/` — contains `interpretations.md` (read-only historical log).
- `<OUTPUT_DIR>/` — write your generated review report here.

---

## Execution Steps

1. **Context Checkout**: Run the `create_context` bash command above to retrieve the interpretations log from the database.
2. **Review Interpretations**: Read through the entire `<CONTEXT_DIR>/interpretations/interpretations.md` file, paying special attention to the latest added experiment section.
3. **Analyze for Inconsistencies**: Assess whether recent conclusions conflict with previous findings, or whether recent findings raise unresolved questions that should be documented as open issues.
4. **Draft Review Report**: Write a report named `review.md` (this exact filename is required) in your `<OUTPUT_DIR>/`:
   - List all identified inconsistencies, conflicts, or gaps.
   - For each issue, specify which experiment sections/IDs are in conflict and why.
   - If no issues are found, explicitly document that the interpretations log is consistent.
5. **Store Results**: Persist the review report to the database:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results \
       --from_agent_type review-interpretations \
       --from_folder <OUTPUT_DIR> \
       --parent_interpretations <I_ID>
   ```
   *Note down the returned review ID as the result of this skill.*
