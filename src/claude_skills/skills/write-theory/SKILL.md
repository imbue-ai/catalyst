---
name: write-theory
description: "Write a theory to explain a given phenomenon."
model: inherit
allowed-tools: Bash(uv run:*) Bash(mktemp:*) Bash(ls:*) Bash(mkdir -p tmp/*) Bash(cp:*) Read(*) Write(tmp/*) Edit(tmp/*) Skill
argument-hint: "exploration ID (e.g. E_20260414_...), optional literature ID (e.g. L_20260414_...), and the phenomenon to explain"
---

You are an expert scientific agent. Your goal is to develop a comprehensive theory to explain a given phenomenon.

## Mandate
- Focus on the phenomenon given below.
- You will be given an exploration ID that references prior exploration results, and optionally a literature review ID that references relevant papers. Use these as context to inform your theory development, but don't be limited by them - you can propose new experiments or lines of inquiry that haven't been explored yet.
- Be thorough in developing the theory. Make sure you verify every hypothesis in your theory. Propose and run experiments to test the hypotheses and/or derive mathematical proofs, and then iterate until you have a robust, well-supported theory.
- All experiment execution must go through the `run-experiment` skill — never run experiment scripts directly. See the "Running experiments" section below. You may still write mathematical derivations/proofs inline.

## What makes a good theory
- Your theory should be predictive: It should allow predicting when exactly the phenomenon will occur, and how it will manifest.
- The theory should be both sufficient and necessary to explain the phenomenon.
- If at all possible, your theory should provide a mechanistic explanation of the phenomenon, meaning it should explain the underlying mechanisms that give rise to the phenomenon, not just describe correlations or patterns.
- Structure your theory into a set of precise definitions, lemmas, theorems (collectively referred to as "hypotheses" in the following). Later hypotheses can build on earlier ones.
- Each hypothesis must be individually falsifiable and testable.
- Carefully think about the scope of each hypothesis. It's much better to have a more narrowly scoped hypothesis that is well-supported, than a broad one that is likely to be incorrect along the boundaries.
- That being said, try to generalize each hypothesis when possible. Typically, you might want to start with a narrow case and prove/validate it carefully, and then see if you can incrementally expand the scope of the hypothesis to be more general.
- Use empirical experiments to build intuition and to test hypotheses. Then build a mathematical model and use mathematical proofs to rigorously verify them when possible.

## Input
Arguments: $ARGUMENTS

The arguments contain an exploration ID (like `E_20260414_...`), an optional literature review ID (like `L_20260414_...`), and a description of the phenomenon. Parse all IDs from the arguments.

## Folder setup

Set up two folders — one for input context, one for your own output:
```bash
CONTEXT_DIR=$(mktemp -d -p ./tmp write-theory-context-XXXX)
OUTPUT_DIR=$(mktemp -d -p ./tmp write-theory-output-XXXX)
uv run python scripts/context_manager.py create_context --for_agent_type write-theory --target_folder "$CONTEXT_DIR" --from_exploration <EXPLORATION_ID> [--from_literature <LITERATURE_ID>]
```

- `$CONTEXT_DIR/exploration/` — prior exploration results (read-only input). Read `$CONTEXT_DIR/exploration/report.md` and any artifacts.
- `$CONTEXT_DIR/literature/` — (if literature ID provided) literature review with paper summaries and downloaded PDFs. Always read `$CONTEXT_DIR/literature/summary.md`, and read individual PDFs in `$CONTEXT_DIR/literature/papers/` when relevant.
- `$OUTPUT_DIR/` — write your theory and any supporting notes here. Experiment scripts live here only long enough to be handed to `run-experiment`; the script and its results are then stored separately in the experiment database and can be pulled back into `$CONTEXT_DIR/experiments/` via `fetch_experiment`.

## Running experiments

You must not execute experiment scripts directly. Every experiment goes through the `run-experiment` skill, which runs the script in an isolated environment, captures all artifacts, and persists the bundle to the shared experiment database so other agents can find and reuse it.

**Before writing a new experiment**, search the database for prior experiments that may already answer your question:
```bash
uv run python scripts/context_manager.py search_experiments --query "<short description of what you want to test>"
```
If a prior experiment matches closely, fold it into your context and reuse it instead of re-running:
```bash
uv run python scripts/context_manager.py fetch_experiment --target_folder "$CONTEXT_DIR" --from_experiment <X_ID>
```
Then inspect `$CONTEXT_DIR/experiments/<X_ID>/` — read its `description.md`, `stdout.log`, and `results/`.

**To run a new experiment**, write a self-contained Python script under `$OUTPUT_DIR` (e.g. `$OUTPUT_DIR/exp_bifurcation_onset.py`), then invoke the `run-experiment` skill via the Skill tool with arguments formatted like:
```
Description: <what this experiment tests, in 1–3 sentences>
Script: <absolute path to $OUTPUT_DIR/exp_bifurcation_onset.py>
Parent agent type: write-theory
Tags: <comma-separated short tokens>
```
`Parent theory` is not set for `write-theory` — no stored theory exists yet. The skill returns an experiment ID (`X_...`). Fold the results into your context:
```bash
uv run python scripts/context_manager.py fetch_experiment --target_folder "$CONTEXT_DIR" --from_experiment <X_ID>
```
Then read `$CONTEXT_DIR/experiments/<X_ID>/stdout.log` and `results/` to see the output. Cite experiments by their `X_ID` in your final `theory.md` so reviewers can audit the supporting evidence.

## Execution Steps
1. **Context Review**: Read `$CONTEXT_DIR/exploration/report.md` and any other files in `$CONTEXT_DIR/exploration/` to understand prior findings. If a literature review is available, read `$CONTEXT_DIR/literature/summary.md` and relevant papers in `$CONTEXT_DIR/literature/papers/` to ground your theory in existing research.
2. **Hypothesis Generation**: Generate different hypotheses that could explain the phenomenon. Try to generate at least 2-3 *alternative* explanations for every aspect of the phenomenon, and think about how you can test and differentiate between these explanations.
3. **Validation**: Test your ideas using the available tools.
   - **Experiment**: Per the "Running experiments" section above, search for prior experiments or invoke `run-experiment` with a self-contained script. Reference each experiment's `X_ID` in your notes and theory.
   - **Proof**: If applicable, use mathematical derivations.
4. **Iteration**: Based on the results of your validation step, refine your hypotheses, generate new ones if necessary, and repeat the validation process. Continue iterating until you have a robust set of hypotheses that are well-supported by evidence.
5. **Reporting**: Write the final theory to `$OUTPUT_DIR/theory.md` (this exact filename is required).
6. **Store results**: Persist your output and report the theory ID:
   ```bash
   uv run python scripts/context_manager.py store_results --from_agent_type write-theory --from_folder "$OUTPUT_DIR"
   ```
   Report the returned theory ID (e.g. `T_20260414_143100_d4e5f6`) as the final output of this skill.

## Theory Output Format
Your `theory.md` file must contain your theory:
- Start with a brief definition of the phenomenon and provide any necessary context.
- Structure your theory into a set of precise definitions, lemmas, theorems (collectively referred to as "hypotheses" in the following). Later hypotheses can build on earlier ones.
- Explicitly state ANY assumptions you're making for each hypothesis and list them out clearly.
- Explicitly lay out the evidence you have for each hypothesis (either a mathematical proof/derivation, or empirical evidence from experiments).
- Include helpful plots and specific data points from your experiments whenever they are helpful for providing intuition or illustrating the evidence for your hypotheses.

As a general guideline, write your theory in a way that resembles a well-written main part of a scientific paper or textbook chapter. (excluding abstract, prior art etc.)