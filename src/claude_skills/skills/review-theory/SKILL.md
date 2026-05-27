---
name: review-theory
description: "Review all theorems/lemmas in a theory and suggest expansions"
argument-hint: "theory ID (e.g. T_20260414_143100_d4e5f6)"
---

You are the **Theory Review Coordinator**. Your task is to extract the lemmas, theorems and observations from a given theory file, and spawn independent background agents to review each of them.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_20260414_...`). Parse the theory ID from the arguments.

## Folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else.

Set up a context folder for your input:
CONTEXT_DIR: `mktemp -d -p ./tmp review-theory-context-XXXX`

Run this command to populate the context:
```bash
uv run python scripts/context_manager.py create_context --for_agent_type review-theory --target_folder <CONTEXT_DIR> --from_theory <THEORY_ID>
```

- `<CONTEXT_DIR>/theory/theory.md` — the theory file to review (read-only input).

## Execution Steps
1. **Context Checkout**: Run the bash command above to retrieve the `theory.md` file using `context_manager.py`.
2. **Review & Extraction**: Read `<CONTEXT_DIR>/theory/theory.md` to determine a list of lemmas, corollaries, theorems and observations within the `theory.md` file.
3. **Spawn Agents**: Launch the following agents in parallel:
   - For each theorem, lemma, corollary, and observation, spawn an agent instructed to invoke the `falsify-hypothesis` skill, passing the `<THEORY_ID>` and theorem/lemma/corollary/observation name and number.
   - Spawn **one** agent instructed to invoke the `suggest-expansions` skill, passing only `<THEORY_ID>`. This agent reviews the entire theory at once.
   - Use the available tools to spawn independent agents (e.g., via `Agent`). All agents can run in parallel.
4. **Collection**: Wait for *all subagents to finish* and collect their final result messages. Each agent's response should contain a review ID (e.g. `R_20260414_143200_g7h8i9`). Note that the subagents might take a long time to finish (up to several hours), so please allow enough time for them to complete fully. Don't conclude prematurely that a subagent has failed when it's actually still running and not finished yet.
5. **Final Output**: Report the list of all review IDs (from the falsification reviews and the expansion review) as the skill's final result.
