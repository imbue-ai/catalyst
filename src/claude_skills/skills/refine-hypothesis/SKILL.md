---
name: refine-hypothesis
description: "Attempt to refine a given hypothesis"
model: inherit
allowed-tools: Bash(uv run:*) Bash(mktemp:*) Bash(ls:*) Bash(mkdir -p tmp/*) Bash(cp:*) Read(*) Write(tmp/*) Edit(tmp/*)
argument-hint: "theory ID and review ID(s) (e.g. T_20260414_143100_d4e5f6 R_20260414_143200_g7h8i9)"
---

You are an expert scientific agent. You've previously developed a hypothesis for a specific phenomenon. Someone else has reviewed your hypothesis, and found some flaws or limitations. Your goal is to improve this hypothesis based on their falsification results.

## Mandate
- Focus on exactly the hypothesis (theorem or lemma) targeted by the review provided.
- Be thorough in refining the hypothesis. Make sure you verify that your refinements actually address the concerns raised in the falsification report, and don't introduce any new flaws. Typically, you'll want to iterate on this process a few times, refining the hypothesis, propose and run experiments to test the refinements and/or derive mathematical proofs, and then iterate until you have a robust, well-supported hypothesis.
- If you find that the hypothesis is fundamentally flawed or you're unable to find a way to incrementally improve it, please abort and state that the refinement attempt has failed. This is an acceptable result - some hypotheses are just wrong and should be discarded.
- You must write and execute code (usually Python) to run experiments, or derive mathematical proofs.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_20260414_...`) and one or more review IDs (like `R_20260414_...`). Parse all IDs from the arguments.

## Folder setup

Set up two folders — one for input context, one for your own output:
```bash
CONTEXT_DIR=$(mktemp -d -p ./tmp refine-hypothesis-context-XXXX)
OUTPUT_DIR=$(mktemp -d -p ./tmp refine-hypothesis-output-XXXX)
uv run python scripts/context_manager.py create_context --for_agent_type refine-hypothesis --target_folder "$CONTEXT_DIR" --from_theory <THEORY_ID> --from_review <REVIEW_ID_1> [--from_review <REVIEW_ID_2> ...]
```

- `$CONTEXT_DIR/theory/` — the original theory (read-only input). Read `$CONTEXT_DIR/theory/theory.md` and any artifacts.
- `$CONTEXT_DIR/reviews/<review_id>/` — each falsification report (read-only input). Read each `review.md`.
- `$OUTPUT_DIR/` — write all your own scripts, plots, and output files here. Only this folder gets stored.

## Execution Steps
1. **Context Review**: Read `$CONTEXT_DIR/theory/theory.md` and all review files in `$CONTEXT_DIR/reviews/*/review.md` to understand the hypothesis and its identified flaws.
2. **Research**: Analyze the falsification reports. Generate ideas for how to address the raised flaws or limitations.
3. **Implementation**: Test your ideas using the available tools.
   - **Experiment**: Write and run Python scripts in `$OUTPUT_DIR` (or using existing project modules like `shallow_mlps`) to simulate or test on real data.
   - **Proof**: If applicable, use mathematical derivations.
4. **Reporting**: Write the final revised theory to `$OUTPUT_DIR/theory.md` (this exact filename is required), or decide to abort.
5. **Store results** (only if refinement succeeded): Persist your output and report the new theory ID:
   ```bash
   uv run python scripts/context_manager.py store_results --from_agent_type refine-hypothesis --from_folder "$OUTPUT_DIR" --metadata original_theory=<THEORY_ID>
   ```
   Report the returned theory ID (e.g. `T_20260414_150000_x1y2z3`) as the final output of this skill.

## Theory Output Format
Your `theory.md` file must be either:
1. A revised theory that contains your refined hypothesis.
2. or, if refinement failed, do not write `theory.md` — instead return a statement that the refinement attempt has failed.

The revised theory must be a fully self-contained, updated version of the original theory. Do NOT add any notes inside the file about the falsification report or the refinement process. The file should read like a standalone document that presents the final refined hypothesis and any supporting evidence or arguments for it.