---
name: refine-hypothesis
description: "Attempt to refine a given hypothesis"
allowed-tools: Bash(uv run:*) Bash(mktemp:*) Bash(ls:*) Bash(mkdir -p tmp/*) Bash(cp:*) Read(*) Write(tmp/*) Edit(tmp/*) Skill
argument-hint: "theory ID, review ID(s), and optional literature ID(s) (e.g. T_20260414_143100_d4e5f6 R_20260414_143200_g7h8i9 L_20260414_151000_j0k1l2)"
---

You are an expert scientific agent. You've previously developed a hypothesis for a specific phenomenon. Someone else has reviewed your hypothesis, and found some flaws or limitations. Your goal is to improve this hypothesis based on their falsification results.

## Mandate
- Focus on exactly the hypothesis (observation, theorem or lemma) targeted by the review provided.
- Be thorough in refining the hypothesis. Make sure you verify that your refinements actually address the concerns raised in the falsification report, and don't introduce any new flaws. Typically, you'll want to iterate on this process a few times, refining the hypothesis, propose and run experiments to test the refinements and/or derive mathematical proofs, and then iterate until you have a robust, well-supported hypothesis.
- If experiments or derivations surface a surprising phenomenon, an unfamiliar mathematical structure, or a claim you're not confident about, invoke the `search-literature` skill to look up prior work before committing to a refinement. See the "Literature grounding" section below.
- If you find that the hypothesis is fundamentally flawed or you're unable to find a way to incrementally improve it, please abort and follow the instructions in the "Discarding a flawed hypothesis" section. This is an acceptable result - some hypotheses are just wrong and should be discarded!
- All experiment execution must go through the `run-experiment` skill — never run experiment scripts directly. See the "Running experiments" section below. You may still write mathematical derivations/proofs inline.

## Discarding a flawed hypothesis
IF you determine that the hypothesis is fundamentally flawed and cannot be reasonably refined, you should remove it from the theory, along with any other hypotheses or sections that were dependent on it, either directly or indirectly:
1. Carefully review the theory and identify all corollaries, lemmas, theorems, or other sections that either mention the flawed hypothesis, or were clearly relying on it.
2. Repeat this process recursively until you've identified all hypotheses and sections that are dependent on the flawed hypothesis *either directly or indirectly*.
3. Remove the flawed hypothesis itself from the theory
4. For each dependent hypothesis and section, check if there's a straight-forward edit to that hypothesis/section that you can make to avoid the dependency. Otherwise, remove the dependent hypotheses/section from the theory alltogether. Repeat for each dependent hypothesis/section until you've either removed or edited all of them.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_20260414_...`), one or more review IDs (like `R_20260414_...`), and optionally one or more literature review IDs (like `L_20260414_...`). Parse all IDs from the arguments.

## Folder setup

Set up two folders — one for input context, one for your own output, and initialize the output folder with the original theory files:
```bash
CONTEXT_DIR=$(mktemp -d -p ./tmp refine-hypothesis-context-XXXX)
OUTPUT_DIR=$(mktemp -d -p ./tmp refine-hypothesis-output-XXXX)
uv run python scripts/context_manager.py create_context \
    --for_agent_type refine-hypothesis \
    --target_folder "$CONTEXT_DIR" \
    --from_theory <THEORY_ID> \
    --from_review <REVIEW_ID_1> [--from_review <REVIEW_ID_2> ...] \
    [--from_literature <LITERATURE_ID_1> --from_literature <LITERATURE_ID_2> ...]
cp -r "$CONTEXT_DIR/theory/"* "$OUTPUT_DIR/"
```

- `$CONTEXT_DIR/theory/` — the original theory (read-only input). Read `$CONTEXT_DIR/theory/theory.md` and any artifacts.
- `$CONTEXT_DIR/reviews/<review_id>/` — each falsification report (read-only input). Read each `review.md`.
- `$CONTEXT_DIR/literature/<literature_id>/` — (if any literature IDs provided, or added mid-run) each literature review, with `summary.md` and downloaded PDFs in `papers/`. Read each `summary.md` and consult individual PDFs when relevant.
- `$OUTPUT_DIR/` — write your refined theory and any supporting notes here. Experiment scripts live here only long enough to be handed to `run-experiment`; the script and its results are then stored separately in the experiment database and can be pulled back into `$CONTEXT_DIR/experiments/` via `fetch_experiment`.

## Running experiments

You must not execute experiment scripts directly. Every experiment goes through the `run-experiment` skill, which runs the script in an isolated environment, captures all artifacts, and persists the bundle to the shared experiment database so other agents can find and reuse it.

**Before writing a new experiment**, search the database for prior experiments that may already answer your question. Prefer filtering by the theory you are refining:
```bash
uv run python scripts/context_manager.py search_experiments --query "<short description>" --parent_theory <THEORY_ID>
```
If a prior experiment matches, fold it into your context and reuse it:
```bash
uv run python scripts/context_manager.py fetch_experiment --target_folder "$CONTEXT_DIR" --from_experiment <X_ID>
```
Then inspect `$CONTEXT_DIR/experiments/<X_ID>/` — read `description.md`, `stdout.log`, and `results/`.

**To run a new experiment**, write a self-contained Python script under `$OUTPUT_DIR` (e.g. `$OUTPUT_DIR/exp_refinement_check.py`). Make sure that the experiment script writes all result files into the directory it runs in (cwd). Then invoke the `run-experiment` skill via the Skill tool with arguments like:
```
Description: <complete explanation of what this experiment tests - include the motivation and summary of the setup. Do NOT reference sections from the theory just by their title or theorem number. Instead, summarize the relevant claim being tested. The reader of the description might not have the theory available.>
Script: <absolute path to the .py file under $OUTPUT_DIR>
Parent theory: <THEORY_ID>
Parent review: <REVIEW_ID>
Parent agent type: refine-hypothesis
Tags: <comma-separated short tokens>
```
The skill returns an experiment ID (`X_...`). Fold the results into your context:
```bash
uv run python scripts/context_manager.py fetch_experiment --target_folder "$CONTEXT_DIR" --from_experiment <X_ID>
```
Cite each experiment by its `X_ID` in your refined `theory.md` so reviewers can audit the evidence.

## Literature grounding

You may start with zero, one, or many literature reviews already in `$CONTEXT_DIR/literature/`. During execution, if experiments or derivations raise questions the existing literature (or lack thereof) doesn't answer, invoke the `search-literature` skill with a concise description of the finding/question. It will return a new literature ID (`L_...`). Fold it into your context without rebuilding the folder:

```bash
uv run python scripts/context_manager.py fetch_literature \
    --target_folder "$CONTEXT_DIR" \
    --from_literature <NEW_L_ID>
```

Then read `$CONTEXT_DIR/literature/<NEW_L_ID>/summary.md` and incorporate its findings into your refinement. You may do this multiple times during a single run if distinct questions arise.

## Execution Steps
1. **Context Review**: Read `$CONTEXT_DIR/theory/theory.md`, all review files in `$CONTEXT_DIR/reviews/*/review.md`, and (if present) each `$CONTEXT_DIR/literature/*/summary.md` to understand the hypothesis, its identified flaws, and any prior literature grounding.
2. **Research**: Analyze the falsification reports. Generate ideas for how to address the raised flaws or limitations.
3. **Implementation**: Test your ideas using the available tools.
   - **Experiment**: Per the "Running experiments" section above, search the database for prior experiments or invoke `run-experiment` with a self-contained script. Reference each experiment's `X_ID` in your notes and refined theory.
   - **Proof**: If applicable, use mathematical derivations.
   - **Literature check (optional)**: If something surprising surfaces, invoke `search-literature` per the "Literature grounding" section and integrate its findings before finalizing the refinement.
4. **Reporting**: Write the final revised theory to `$OUTPUT_DIR/theory.md` (this exact filename is required), or decide to abort.
5. **Store results** Persist your output and report the new theory ID:
   ```bash
   uv run python scripts/context_manager.py store_results --from_agent_type refine-hypothesis --from_folder "$OUTPUT_DIR" --metadata original_theory=<THEORY_ID>
   ```
   Report the returned theory ID (e.g. `T_20260414_150000_x1y2z3`) as the final output of this skill.

## Theory Output Format
Your `theory.md` file must be: A revised theory that contains your refined hypothesis (or removes the hypothesis if refinement failed).

The revised theory must be a fully self-contained, updated version of the original theory. Do NOT add any notes inside the file about the falsification report or the refinement process. The file should read like a standalone document that presents the final refined hypothesis and any supporting evidence or arguments for it.
