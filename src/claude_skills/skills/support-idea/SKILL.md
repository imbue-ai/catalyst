---
name: support-idea
description: "Run experiments and derive mathematical proofs to support a pre-existing theory idea supplied as a latex/pdf/markdown file or argument."
argument-hint: "Either: path to the pre-existing theory file (.tex, .pdf, or .md) and any optional scoping notes (e.g. 'focus on Theorem 3'), OR a short description of the theory idea"
---

You are an expert scientific agent. Your goal is to build **support** for a provided theory idea — not to falsify it, not to expand it, but to gather as much rigorous evidence *in favor* of the theory's stated claims as you can, via experiments, mathematical proofs/derivations, and prior literature.

## Mandate
- The theory you are supporting comes from an external file (latex, pdf, or markdown) or a short description provided as an argument. Treat its statements (definitions, conjectures, observations, lemmas, theorems) as fixed inputs — do not rewrite or reinterpret them. Your job is to *strengthen the evidence* behind each one. You *can* however add additional intermediate lemmas or propositions if they help build the case for the main statements.
- For every non-trivial statement in the theory, aim to provide at least one of: a mathematical proof/derivation, an experimental result, or a citation of prior literature that directly supports it. Prefer multiple independent lines of support when feasible.
- You must run a literature review **inline** via the `search-literature` skill to ground the theory in prior work. Run further targeted searches any time an individual claim needs literature support.
- All experiment execution must go through the `run-experiment` skill. See the "Running experiments" section below.
- If you discover that a statement genuinely cannot be supported (you tried and failed to prove it and experiments contradict it), note this honestly in a dedicated "Unsupported Claims" section — do not fabricate evidence. Supporting a theory means making the strongest honest case for it, not pretending every claim holds.

## Input
Arguments: $ARGUMENTS

The arguments contain either:
1. a path to the pre-existing theory file (with extension `.tex`, `.pdf`, or `.md`), or
2. a short description of the theory idea

It might optionally include free-form scoping notes.

## Folder setup
Set up two folders — one for input context, one for your own output:
CONTEXT_DIR: `mktemp -d -p ./tmp support-idea-context-XXXX`
OUTPUT_DIR: `mktemp -d -p ./tmp support-idea-output-XXXX`

If the input theory is provided as a file, copy the provided theory file into the context folder so it lives at a stable path for the rest of the run:
```bash
cp "<INPUT_FILE_PATH>" "<CONTEXT_DIR>/source_theory.<ext>"
```

- `<CONTEXT_DIR>/source_theory.{tex,pdf,md}` — the pre-existing theory (read-only input).
- `<CONTEXT_DIR>/literature/<literature_id>/` — populated mid-run as you call `search-literature` and fold results in via `fetch_literature`. Each folder contains a `summary.md` and downloaded PDFs under `papers/`.
- `<OUTPUT_DIR>/` — write your supported theory, experiments, and supporting notes here.

Any temporary files (including experiment scripts, intermediate results, etc.) must be stored only under `<OUTPUT_DIR>`.

## Reading the input theory
- `.md` / `.tex`: read with the `Read` tool directly.
- `.pdf`: read with the `Read` tool (it handles PDFs natively). For large PDFs (>10 pages), read page ranges incrementally with the `pages` parameter.

Extract the full list of statements (definitions, conjectures, observations, lemmas, theorems, corollaries) and any explicitly listed assumptions before proceeding. Write this list to `<OUTPUT_DIR>/statements.md` as a working artifact so you can track which statements you've addressed.

If the input is a markdown or tex file and references images, copy those images into the context folder as well. Later, you'll want to make sure to copy any images that you'd like to preserve into the output folder, and update their relative paths in the final `theory.md` accordingly.

## Inline literature review
You **must** run the `search-literature` skill at least once at the start of this skill to ground the theory in prior work, and again whenever a specific claim needs narrower literature support.

1. **Initial pass**: Invoke `search-literature` with a description of the theory's overall topic + its most load-bearing claims. This returns a literature ID (`L_...`).
2. **Targeted passes** (optional, repeat as needed): As you work through individual statements, if a claim calls for evidence from prior work (e.g. a specific technique, a known bound, a reported empirical finding), invoke `search-literature` again with a focused query for that claim. Each call returns a new `L_...` ID.

After each `search-literature` call, fold its result into the context folder so you can read it alongside the theory:
```bash
uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" fetch_literature \
    --target_folder <CONTEXT_DIR> \
    --from_literature <NEW_L_ID>
```
Then read `<CONTEXT_DIR>/literature/<NEW_L_ID>/summary.md` and consult individual PDFs under `papers/` when needed.

## Running experiments
Every experiment, test, and validation must be set up and run through the `run-experiment` skill, using the AGENT_TYPE `support-idea`.
Cite each experiment by its `X_ID` in your final `theory.md` under the statement it supports, so reviewers can audit the evidence.

Useful experiment patterns for this skill:
- **Direct verification**: Reproduce a claimed prediction of the theory and confirm the predicted behavior.
- **Robustness checks**: Test the claim across a range of hyperparameters, seeds, or input distributions to demonstrate it is not a one-off.
- **Cross-regime confirmation**: Verify a claim holds in regimes that weren't the theory's original focus, to strengthen the case.

## Execution Steps
1. **Parse input**: Extract the file path or theory idea, and any potential scoping notes from `$ARGUMENTS`. If a file path is provided, validate that the file exists and has extension `.tex`, `.pdf`, or `.md`. Copy it into `<CONTEXT_DIR>` as described in "Folder setup".
2. **Extract statements**: Read the source theory and produce `<OUTPUT_DIR>/statements.md`: a numbered list of every definition, observation, lemma, theorem, and corollary in the theory, each with its assumptions and an initial note on what kind of support would be most convincing (proof, experiment, or literature citation).
3. **Initial literature review**: Invoke `search-literature` with the theory's topic + its top 2–3 load-bearing claims, then fold the result into `<CONTEXT_DIR>` as described above. Read the resulting `summary.md`.
4. **Reproduce a base case**: Before you continue, make sure you can successfully reproduce a base case of the phenomenon. Use `run-experiment`, and find the hyper-parameters that most clearly illustrate the phenomenon. You might get a good figure out of this step for inclusion in your theory.
5. **Plan**: For each statement in `statements.md`, decide on a support strategy (proof, experiment, literature citation, or combination). Prioritize the theory's most central / most uncertain statements.
6. **Gather support**: Work through the statements. For each:
   - **Proof**: If the statement is formally provable, derive a rigorous mathematical proof. Show all steps — do not hand-wave.
   - **Experiment**: Invoke `run-experiment` (AGENT_TYPE `support-idea`). Design the experiment to test a specific prediction the statement makes; record the experiment's `X_ID`.
   - **Literature**: If prior work directly supports the claim, cite it from the literature review. If you need narrower support for this specific claim, invoke `search-literature` again with a targeted query, fold the new `L_ID` into `<CONTEXT_DIR>`, and cite the relevant paper(s).
7. **Iterate**: If an experiment or derivation comes back ambiguous or negative, do not abandon the statement immediately — try a refined experimental setup or an alternative proof strategy. Only record a statement as unsupported after genuinely exhausting reasonable approaches.
8. **Reporting**: Write the final supported theory to `<OUTPUT_DIR>/theory.md` (this exact filename is required). Add plots and figures generated by your experiments; you may also generate additional illustrative plots with Python scripts as needed.
9. **Store results**: Persist your output and return the theory ID:
   ```bash
   uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" store_results --from_agent_type support-idea --from_folder <OUTPUT_DIR>
   ```
   Note down the returned theory ID (e.g. `T_20260421_150000_x1y2z3`) as the result of this skill.

## Theory Output Format
Your `theory.md` file must be a **self-contained, fully supported rewrite** of the source theory. Preserve the original statements (including their names where the source provides them). Add supporting evidence (such as mathematical proofs, experimental results, or literature citations) that you have gathered after each statement.

Follow these guidelines when writing the `theory.md` file:
- Start with a brief definition of the phenomenon and provide any necessary context, including a brief summary of the relevant literature.
- Then, provide a short intuitive explanation of your theory and how it explains the phenomenon. In the sections afterwards, follow up with rigorous mathematical statements or empirical observations to substantiate the intuition.
- Structure the rigorous part of your theory into a set of precise definitions, conjectures, observations, lemmas and theorems (collectively referred to as "statements" in the following). Only call something a lemma or theorem if you can formally prove it! Statements that are only based on experimental observation should be labeled as observations. Later statements can build on earlier ones.
- Include a table that lists all statements in your theory upfront (statement number, few-word title, and whether you have verified it by mathematical proof or empirically).
- Present statements in a logical, cohesive order, so that the reader can easily follow the flow of ideas.
- Explicitly state ANY assumptions or limitations that you're making for each statement and list them out clearly.
- Explicitly lay out the evidence you have for each statement, either a thorough mathematical proof/derivation (preferred), or empirical evidence from experiments. You can also cite prior literature to support your statements. Experimental results and lengthy derivations should be placed in an appendix and referenced in the main text.
- Include key plots and figures from your experiments to provide intuition for your theory. Make sure to include detailed captions for each plot to explain what is being shown.
- Image references in the markdown file need to be relative to `<OUTPUT_DIR>`. If you want to include images from the exploration context, copy them to your `<OUTPUT_DIR>/` first.
- Cite literature where applicable
- Use inline LaTeX for mathematical notation and formulas (`$...$` for inline math, and `$$...$$` for display math). Do NOT put formulas into code blocks.

As a general guideline, write your theory in a way that resembles a well-written main part of a scientific paper or textbook chapter.