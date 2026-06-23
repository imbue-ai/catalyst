---
name: rank-proposals
description: "Compare and rank multiple proposals (experiments, literature searches, and solution candidates), separating solution candidates from other proposals."
argument-hint: "multiple proposal IDs (e.g. O_20260616_111111_aaaaaa O_20260616_222222_bbbbbb)"
---

# Rank Proposals

You are an expert scientific agent. Your goal is to review, compare, and rank multiple alternative proposals (which may include regular experiments, literature searches, and solution candidates).

## Mandate & Grouping Rules
1. **Identify Proposal Types**: Check each checked-out proposal to determine its type by reading its `proposal.md` header (e.g. `# Experiment Proposal`, `# Literature Search Proposal`, or `# Solution Candidate Proposal`).
2. **Experiment & Literature Search Proposals**:
   - Group all regular experiment proposals and literature search proposals together.
   - Critically compare and rank them into a single ordered list (`rankings`), from best/highest priority to worst/lowest priority.
   - Evaluate them based on:
     - **Expected Value**: How much the proposal's findings would reduce uncertainty or move closer to the optimization goal.
     - **Feasibility & Soundness**: How well-designed the script or search methodology is, and whether the approach is robust.
     - **Cost-Benefit Tradeoff**: The value of the potential findings compared to the estimated resource cost, complexity, and runtime. Literature search proposals can be assumed to be cheap, about ~5 minutes in runtime.
   - Remove duplicates: If multiple experiment or literature search proposals are effectively the same (identical or very similar experiment setup or search prompt), only keep the best-ranked one among those and discard the other equivalent ones in your ranking.
3. **Solution Candidate Proposals**:
   - Do NOT rank solution candidate proposals together with experiments or literature searches.
   - Collect all solution candidate proposals into a separate, unranked list (`solution_candidates`).

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
    --for_agent_type rank-proposals \
    --target_folder <CONTEXT_DIR> \
    --from_proposal <O_ID_1> --from_proposal <O_ID_2> [--from_proposal <O_ID_3> ...]
```

Context layout:
- `<CONTEXT_DIR>/proposals/<O_ID>/` — contains a folder for each checked-out proposal containing:
  - `proposal.md` (detailing the proposal)
  - Optional companion files (such as `script.py` for experiments/solutions).

---

## Execution Steps

1. **Context Checkout**: Run the `create_context` command above to check out all candidate proposals.
2. **Analyze Proposals**: For each candidate under `<CONTEXT_DIR>/proposals/<O_ID>/`, inspect `proposal.md` to classify it and review its motivation and methodology.
3. **Execute Grouping & Ranking**:
   - Sort the regular experiments and literature searches together, ranking them from highest priority to lowest priority, while removing duplicates.
   - Gather all solution candidates into a separate, unranked collection.
4. **Output Selection & Rankings**: Formulate a numeric ranking for the experiment/literature-search proposals (from 1...n), and list the solution candidates separately. Include both sections in the skill's output.
