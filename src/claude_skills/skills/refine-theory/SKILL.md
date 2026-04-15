---
name: refine-theory
description: "Refine a theory by sequentially applying all its available reviews"
model: inherit
allowed-tools: Bash(uv run:*) Bash(jq:*) Agent TeamCreate TaskCreate TaskUpdate TaskList SendMessage
argument-hint: "theory ID (e.g. T_20260414_143100_d4e5f6)"
---

You are the **Theory Refinement Coordinator**. Your task is to systematically improve a theory by applying all of its reviews sequentially, chaining the resulting improvements.

## Input
Arguments: $ARGUMENTS

Parse the initial theory ID (e.g., `T_20260414_...`) from the arguments.

## Execution Steps

1. **Find Reviews**: Use the bash tool to list all reviews associated with the initial theory:
   ```bash
   uv run python scripts/context_manager.py list --type review --parent_theory <INITIAL_THEORY_ID> --json
   ```
   Parse the JSON output to extract the list of review IDs. If there are no reviews, your job is done and you should return the initial theory ID.

2. **Sequential Refinement**:
   Initialize `CURRENT_THEORY_ID` with your initial theory ID.
   
   For each review ID in the list, *one at a time in sequence*:
     - Spawn a subagent instructed to invoke the `refine-hypothesis` skill.
     - Provide the subagent with the `CURRENT_THEORY_ID` and the specific review ID it needs to process. It should pass both as arguments to the `refine-hypothesis` skill.
     - Wait for the subagent to finish and retrieve the new theory ID it returns.
     - Update `CURRENT_THEORY_ID` to this new theory ID.
     - **CRITICAL**: Do not run these in parallel. The output of one refinement must be the input to the next.

3. **Final Output**: After every review in the list has been processed sequentially, report the final `CURRENT_THEORY_ID` as the result of this skill.
