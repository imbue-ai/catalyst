---
name: refine-theory
description: "Refine a theory by sequentially applying all its available reviews"
allowed-tools: Bash(uv run:*) Bash(jq:*) Agent
argument-hint: "theory ID (e.g. T_20260414_143100_d4e5f6)"
---

You are the **Theory Refinement Coordinator**. Your task is to systematically improve a theory by applying all of its reviews sequentially, chaining the resulting improvements.

## Input
Arguments: $ARGUMENTS

Parse the initial theory ID (e.g., `T_20260414_...`) from the arguments. You might also receive one or multiple literature review IDs (e.g., `L_20260414_...`) as part of your arguments.

## Execution Steps

1. **Find Reviews**: Use the bash tool to list all reviews associated with the initial theory:
   ```bash
   uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" list --type review --parent_theory <INITIAL_THEORY_ID> --json
   ```
   Parse the JSON output to extract the list of reviews. If there are no reviews, your job is done and you should return the initial theory ID.

2. **Classify Reviews**: Separate the reviews into two groups based on their `agent_type` field:
   - **Falsification reviews**: entries where `agent_type` is `"falsify-hypothesis"` — these will be processed via `refine-hypothesis`.
   - **Expansion reviews**: entries where `agent_type` is `"suggest-expansions"` — these will be processed via `expand-theory`.

3. **Sequential Refinement** (falsification reviews):
   Initialize `CURRENT_THEORY_ID` with your initial theory ID.
   
   For each falsification review ID in the list, *one at a time in sequence*:
     - Spawn a subagent instructed to invoke the `refine-hypothesis` skill.
     - Provide the subagent with the `CURRENT_THEORY_ID` and the specific review ID it needs to process. Also pass any literature review IDs you might have. It should pass both as arguments to the `refine-hypothesis` skill.
     - Wait for the subagent to finish and retrieve the new theory ID it returns.
     - Update `CURRENT_THEORY_ID` to this new theory ID.
     - **CRITICAL**: Do not run these in parallel. The output of one refinement must be the input to the next.

4. **Expansion** (expansion reviews):
   Skip this step if ANY of the `refine-hypothesis` subagents reported that they've made significant changes to the theory. Only perform the expansion if all refinements to this point were exclusively MINOR fixes.
   If there are any expansion reviews, and all refinements so far were minor, spawn a single subagent instructed to invoke the `expand-theory` skill.
   - Provide the subagent with `CURRENT_THEORY_ID` (the latest theory after all refinements) and **all** expansion review IDs. Also pass any literature review IDs you might have. It should pass these as arguments to the `expand-theory` skill.
   - Wait for the subagent to finish and retrieve the new theory ID it returns.
   - Update `CURRENT_THEORY_ID` to this new theory ID.

5. **Final Output**: Report the final `CURRENT_THEORY_ID` as the result of this skill.