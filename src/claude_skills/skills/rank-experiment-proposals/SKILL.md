---
name: rank-experiment-proposals
description: "Compare and rank multiple experiment proposals to select the single best next experiment."
argument-hint: "multiple proposal IDs (e.g. O_20260616_111111_aaaaaa O_20260616_222222_bbbbbb)"
---

# Rank Experiment Proposals

You are an expert scientific agent. Your goal is to review, compare, and rank multiple alternative experiment proposals, selecting and outputting the ranking of the proposals directly.

## Mandate
- Critically evaluate each candidate experiment proposal.
- Evaluate each proposal based on:
  - **Expected Value**: How much the experiment's findings would reduce uncertainty or move closer to the optimization goal.
  - **Feasibility & Soundness**: How well-designed the companion script and setup are, and whether the methodology is robust.
  - **Cost-Benefit Tradeoff**: The value of the potential findings compared to the estimated resource cost, complexity, and runtime.
- Do not attempt to store the results via `context_manager.py`, and do not write a file-based report. Instead, output the final ranking (from 1 to n, where 1 is the best and n is the worst) directly as your skill output.

## Input
Arguments: $ARGUMENTS

The arguments contain two or more proposal IDs (like `O_20260616_...`). Parse all IDs from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up a folder for the input context:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp rank-proposals-context-XXXX`

Run this command to populate the context, which retrieves all candidate proposals from the database:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type rank-experiment-proposals \
    --target_folder <CONTEXT_DIR> \
    --from_proposal <O_ID_1> --from_proposal <O_ID_2> [--from_proposal <O_ID_3> ...]
```

### Context Layout
- `<CONTEXT_DIR>/proposals/<O_ID>/` — contains a folder for each proposal, each containing a `proposal.md` and a companion runnable `script.py`.

---

## Execution Steps

1. **Context Checkout**: Run the `create_context` command above to check out all candidate proposals.
2. **Analyze Proposals**: Read and analyze each experiment proposal under `<CONTEXT_DIR>/proposals/<O_ID>/proposal.md` and its companion `<CONTEXT_DIR>/proposals/<O_ID>/script.py`.
3. **Compare and Rank**: Compare all proposals against each other, scoring them by value, feasibility, and cost.
4. **Output Selection & Rankings**: Formulate a numeric ranking from 1 to n for the proposals (where 1 is the best/highest priority and n is the lowest). Include this ranking directly in your final response as the skill's output, structured clearly, for example:
   ```
   1. O_20260616_111111_aaaaaa (Selected: Most promising hyperparameter sweep)
   2. O_20260616_222222_bbbbbb (Strong backup, but slightly higher runtime)
   ```
   Provide a concise, critical rationale for each proposal's position.
