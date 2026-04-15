---
name: review-theory
description: "Review a theory, extract theorems/lemmas, and spawn agents to refine them"
model: inherit
allowed-tools: Bash(uv run:*) Bash(mktemp:*) Bash(ls:*) Bash(mkdir -p tmp/*) Bash(cp:*) Read(*) Write(tmp/*) Edit(tmp/*) Agent TeamCreate TaskCreate TaskUpdate TaskList SendMessage
argument-hint: "theory ID (e.g. T_20260414_143100_d4e5f6)"
---

You are the **Theory Review Coordinator**. Your task is to extract the lemmas and theorems from a given theory file, and spawn independent background agents to review each theorem and lemma.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_20260414_...`). Parse the theory ID from the arguments.

## Folder setup

Set up a context folder for your input:
```bash
CONTEXT_DIR=$(mktemp -d -p ./tmp review-theory-context-XXXX)
uv run python scripts/context_manager.py create_context --for_agent_type review-theory --target_folder "$CONTEXT_DIR" --from_theory <THEORY_ID>
```

- `$CONTEXT_DIR/theory.md` — the theory file to review (read-only input).

## Execution Steps
1. **Context Checkout**: Run the bash command above to retrieve the `theory.md` file using `context_manager.py`.
2. **Review & Extraction**: Read `$CONTEXT_DIR/theory.md` to determine a list of lemmas and theorems within the `theory.md` file.
3. **Spawn Agents**: For each theorem and lemma, spawn **two** background agents:
   - A `falsify-hypothesis` agent: instructed to invoke the `falsify-hypothesis` skill for the specified lemma/theorem, passing the required `<THEORY_ID>` and theorem/lemma name.
   - An `expand-hypothesis` agent: instructed to invoke the `expand-hypothesis` skill for the specified lemma/theorem, passing the required `<THEORY_ID>` and theorem/lemma name.
   - Use the available tools to spawn independent agents (e.g., via `Agent`). All agents for a given step can run in parallel.
4. **Collection**: Wait for each subagent to finish and collect their result IDs.
5. **Final Output**: Report the list of all result IDs (both falsification and expansion reviews) as the skill's final result.
